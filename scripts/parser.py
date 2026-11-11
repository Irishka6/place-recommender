import os
import requests
import sqlite3
import json
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def setup_db():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'data', 'database.db')

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            address TEXT,
            osm_id TEXT,
            gis_id TEXT,
            maps_url TEXT,
            raw_description TEXT,
            comments TEXT,
            ai_summary TEXT,
            rating REAL DEFAULT 5.0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Location_Tags (
            location_id INTEGER,
            tag_id INTEGER,
            FOREIGN KEY(location_id) REFERENCES Locations(id),
            FOREIGN KEY(tag_id) REFERENCES Tags(id),
            UNIQUE(location_id, tag_id)
        )
    ''')

    conn.commit()
    return conn


def search_2gis_places(category, api_key="56570d62-1a63-427a-b4df-4786d2df927d"):
    all_items = []
    max_pages = 5

    for page in range(1, max_pages + 1):
        url = f"https://catalog.api.2gis.com/3.0/items?q={category}&location=37.61556,55.75222&radius=20000&page_size=10&page={page}&key={api_key}"

        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'items' in data['result']:
                    items = data['result']['items']
                    all_items.extend(items)

                    # Если API вернуло меньше 10 элементов, значит мы дошли до конца списка
                    if len(items) < 10:
                        break
                else:
                    # Если ключа items нет (например, результаты закончились), прерываем цикл
                    break
            else:
                print(f"Ошибка API: {response.status_code}")
                break

        except Exception as e:
            print(f"Ошибка поиска {category} в 2GIS (страница {page}): {e}")
            break

        time.sleep(0.5)  # Пауза между запросами страниц, чтобы API не заблокировал IP

    return all_items


def scrape_reviews_with_selenium(gis_id):
    if not SELENIUM_AVAILABLE:
        return []

    url = f"https://2gis.ru/moscow/firm/{gis_id}/tab/reviews"
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # ХАК: Добавляем флаги для обхода блокировок и скрытия автоматизации
    options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)

    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    service = Service(executable_path=r"D:\yandexdriver.exe")
    reviews = []
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(4)  # Увеличили паузу для надежности

        # ВОЗВРАЩЕНО: Блок авто-закрытия всплывающих окон
        try:
            driver.find_element(By.XPATH, "//*[contains(text(), 'Пропустить обновление')]").click()
            time.sleep(2)
        except:
            pass

        try:
            for btn in driver.find_elements(By.XPATH,
                                            "//*[contains(text(), 'Хорошо') or contains(text(), 'Понятно') or contains(text(), 'Принять')]"):
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
        except:
            pass

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        page_text = driver.execute_script("return document.body.innerText;")
        lines = page_text.split('\n')

        for line in lines:
            text = line.strip()
            real_words = [w for w in text.split() if any(c.isalpha() for c in w)]
            is_valid_length = len(real_words) >= 9
            is_not_interface = "2ГИС" not in text and "Условия" not in text and "сортировк" not in text.lower() and "Отзывы" not in text

            if is_valid_length and is_not_interface:
                if text not in reviews:
                    reviews.append(text)
                if len(reviews) == 3:
                    break
    except Exception:
        pass
    finally:
        if driver:
            driver.quit()

    return reviews


def main():
    conn = setup_db()
    cursor = conn.cursor()
    categories = ['Музей', 'Парк', 'Ресторан', 'Кафе', 'Сквер', 'Усадьба', 'Галерея']

    print("Начинаем сбор данных (API 2GIS + Selenium)...\n")

    for category in categories:
        print(f" -> Запрос топ-мест для категории: {category}...")
        places = search_2gis_places(category)

        for place in places:
            try:
                gis_id = str(place.get('id', ''))
                title = place.get('name', 'Без названия')
                address = place.get('address_name', '')
                maps_url = f"https://2gis.ru/moscow/firm/{gis_id}"

                cursor.execute("SELECT id FROM Locations WHERE gis_id = ?", (gis_id,))
                if cursor.fetchone():
                    continue

                raw_text = f"Данные 2GIS: {json.dumps(place, ensure_ascii=False)}."

                try:
                    raw_rating = place.get('rating', 5.0)
                    rating = round(float(raw_rating), 2)
                except (ValueError, TypeError):
                    rating = 5.00

                reviews = scrape_reviews_with_selenium(gis_id)
                comments_text = ' | '.join(reviews) if reviews else "Отзывы скрыты или отсутствуют."

                cursor.execute('''
                    INSERT INTO Locations (title, category, address, osm_id, gis_id, maps_url, raw_description, comments, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title, category, address, "", gis_id, maps_url, raw_text, comments_text, rating))

                conn.commit()
                print(f"    Сохранено: {title} (Рейтинг: {rating:.2f})")

            except Exception as e:
                continue

    conn.close()
    print("\nСбор данных завершен! Переходите к ИИ-обработке.")


if __name__ == "__main__":
    main()