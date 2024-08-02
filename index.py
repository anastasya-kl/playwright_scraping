# імпортування бібліотек
import json
import time
import signal
import sys
import logging
from playwright.sync_api import sync_playwright
import pandas as pd
#  -------------------------------------------

# налаштування логування
logging.basicConfig(filename='scraping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#  -------------------------------------------
#  допоміжні функції

#  функція прокрутки до кінця сторінки
def scroll_to_bottom(page):
    try:
        last_height = page.evaluate('document.body.scrollHeight')
        attempts = 0
        max_attempts = 5
        while attempts < max_attempts:
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(2)
            new_height = page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                attempts += 1
            else:
                attempts = 0
                last_height = new_height
        logging.info("Reached the bottom of the page or maximum scroll attempts")
    except Exception as e:
        logging.error(f"Error while scrolling to bottom: {e}")
        
        
#  функція отримання останнього номеру рядка
def get_last_element_number(page):
    try:
        last_span = page.query_selector('span.sc-f61b72e9-0.iphTVP >> nth=-1 >> span')
        return int(last_span.inner_text()) if last_span else 0
    except Exception as e:
        logging.error(f"Error while getting last element number: {e}")
        return 0

#  функція прокрутки до елемента
def scroll_to_element(page, element_number):
    try:
        page.evaluate(f'''
        const elements = document.querySelectorAll('span.sc-f61b72e9-0.iphTVP > span');
        for (const element of elements) {{
            if (element.innerText === '{element_number}') {{
                element.scrollIntoView();
                break;
            }}
        }}
        ''')
        time.sleep(2)
    except Exception as e:
        logging.error(f"Error while scrolling to element {element_number}: {e}")
# -------------------------------------------

#  основна функція скрапінгу даних
def main(proxy_server=None, proxy_username=None, proxy_password=None):
    try:
        with sync_playwright() as p:
            # підготовка проксі налаштувань, якщо вони надані
            proxy_settings = {}
            if proxy_server:
                proxy_settings["server"] = proxy_server
                if proxy_username and proxy_password:
                    proxy_settings["username"] = proxy_username
                    proxy_settings["password"] = proxy_password

            # ініціалізація браузера з проксі або без нього
            if proxy_settings:
                browser = p.chromium.launch(headless=False, proxy=proxy_settings)
                context = browser.new_context(proxy=proxy_settings)
            else:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
            
            page = context.new_page()
            
            logging.info('Navigating...')
            print('Navigating...')
            page.goto('https://defillama.com/chains')
            logging.info('Navigated! Starting to scrape...')
            print('Navigated! Starting to scrape...')
            
            # гортаємо до кінця сторінки, щоб отримати номер останнього елемента
            scroll_to_bottom(page)
            last_element_number = get_last_element_number(page)
            logging.info(f"Last element number: {last_element_number}")
            print(f"Last element number: {last_element_number}")
            
            # гортаємо назад на початок
            page.evaluate('window.scrollTo(0, 0)')
            time.sleep(2)
            
            data = []
            current_element = 0
            
            # зчитуємо дані до останнього елемента
            while current_element < last_element_number:
                try:
                    # стовпець Name
                    elements  = page.query_selector_all("a.sc-8c920fec-3.dvOTWR")
                    # стовпець Protocol
                    protocols = page.query_selector_all('//*[@id="__next"]/div[1]/div/main/div[2]/div[4]/div[2]/div/div[2]')
                    # стовпець Tvl
                    tvls      = page.query_selector_all('//*[@id="__next"]/div[1]/div/main/div[2]/div[4]/div[2]/div/div[7]')
                    
                    # прохід по знайденим елементам
                    for i, element in enumerate(elements):
                        name = element.inner_text()
                        link = element.get_attribute('href')
                        
                        new_data = {
                            'Name': name,
                            'Link': link,
                            'Protocols': protocols[i].inner_text() if i < len(protocols) else '',
                            'TVL': tvls[i].inner_text() if i < len(tvls) else ''
                        }
                        
                        # перевірка на наявні копії
                        duplicate = next((item for item in data if item['Name'] == name), None)
                        if duplicate:
                            data.remove(duplicate)
                        else:
                            current_element += 1
                            
                        data.append(new_data)
                        logging.info(f"Scraped: {name}")
                        
                        # завершуємо цикл, якщо останній елемент вже був зчитаний
                        if current_element >= last_element_number:
                            break
                
                except Exception as e:
                    logging.error(f"Error during scraping elements: {e}")
                    print(f"Error during scraping elements: {e}")
                
                # переходимо до останнього спарсеного елемента
                scroll_to_element(page, str(current_element))
            
            df = pd.DataFrame(data)
            
            # фінальна перевірка на наявність дублікатів
            df.drop_duplicates(subset=['Name'], keep='first', inplace=True)
            
            logging.info(f"Data scraped successfully. Total unique elements: {len(df)}")
            print(f"Data scraped successfully. Total unique elements: {len(df)}")
            
            # запис даних у файл csv
            df.to_csv('scraped_data.csv', index=False)
            logging.info('Data saved to scraped_data.csv')
            print('Data saved to scraped_data.csv')
            
            # закриття браузера
            browser.close()
    
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")

# -------------------------------------------

#функція призупинення роботи скрипта через обробника сигналів
def signal_handler(sig, frame):
    logging.info('Stopping the script...')
    print('Stopping the script...')
    sys.exit(0)

if __name__ == "__main__":
    # встановлення обробника сигналів
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        try:
            # завантаження параметрів з файлу config.json
            with open('config.json', 'r') as config_file:
                config = json.load(config_file)
            
            # передача параметрів проксі в main
            main(
                proxy_server=config.get('proxy_server'),
                proxy_username=config.get('proxy_username'),
                proxy_password=config.get('proxy_password')
            )
            
            # отримання інтервалу з конфігураційного файлу
            interval = config.get('scrape_interval_minutes', 5)  # значення за замовчуванням 5 хвилин
            logging.info(f"Waiting for {interval} minutes before the next scrape...")
            print(f"Waiting for {interval} minutes before the next scrape...")
            
            # очікування перед наступним виконанням
            time.sleep(interval * 60)
        
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            print(f"Error in main loop: {e}")
            time.sleep(60)  # запобігаємо безперервний цикл
