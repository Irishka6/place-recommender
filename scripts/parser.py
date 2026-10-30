import requests
import sqlite3
import json


# 1. Настройка локальной базы данных SQLite
def setup_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            address TEXT,
            osm_id TEXT,
            gis_id TEXT,
            raw_description TEXT,
            ai_summary TEXT
        )
    ''')
    conn.commit()
    return conn


# 2. Сбор открытых геоданных из OSM (Overpass API)
# 2. Сбор открытых геоданных из OSM (Overpass API)
def get_osm_locations():
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = """
    [out:json];
    area["name"="Москва"]->.searchArea;
    (
      node["tourism"="museum"](area.searchArea);
      node["leisure"="park"](area.searchArea);
    );
    out 100;
    """

    # Добавляем заголовки, чтобы сервер OSM не блокировал запрос
    headers = {
        'User-Agent': 'MoscowVibeMVP/1.0 (local test)',
        'Accept': 'application/json, */*'
    }

    try:
        response = requests.get(overpass_url, params={'data': query}, headers=headers)

        # Проверяем, что сервер ответил кодом 200 (Успех)
        if response.status_code == 200:
            return response.json().get('elements', [])
        else:
            print(f"Ошибка OSM: Сервер вернул код {response.status_code}. Текст: {response.text[:100]}")
            return []

    except requests.exceptions.JSONDecodeError:
        print(f"Ошибка OSM: Получен невалидный JSON. Ответ сервера: {response.text[:100]}")
        return []
    except Exception as e:
        print(f"Сетевая ошибка при обращении к OSM: {e}")
        return []


# 3. Интеграция с официальным API 2GIS
def get_2gis_data(query_text, api_key="56570d62-1a63-427a-b4df-4786d2df927d"):
    # Эндпоинт поиска филиалов. В дальнейшем сюда добавятся методы для отзывов.
    url = f"https://catalog.api.2gis.com/3.0/items?q={query_text}&location=37.61556,55.75222&radius=20000&key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'items' in data['result']:
                return data['result']['items'][0]  # Берем наиболее релевантное совпадение
    except Exception as e:
        print(f"Ошибка запроса к 2GIS: {e}")
    return None


# 4. Основной пайплайн офлайн-сбора
def main():
    conn = setup_db()
    cursor = conn.cursor()

    print("Начинаем выгрузку базы по Москве из OSM...")
    osm_places = get_osm_locations()

    for place in osm_places:
        osm_id = str(place.get('id', ''))
        tags = place.get('tags', {})

        title = tags.get('name', 'Без названия')
        category = 'Музей/Парк'
        address = f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip()

        print(f"Обогащение через 2GIS: {title}...")
        gis_data = get_2gis_data(title)
        gis_id = str(gis_data.get('id', '')) if gis_data else ''

        # Сборка сырого текста для будущей обработки нейросетью
        raw_text = f"Теги OSM: {json.dumps(tags, ensure_ascii=False)}."
        if gis_data:
            raw_text += f" Данные 2GIS: {json.dumps(gis_data, ensure_ascii=False)}"

        cursor.execute('''
            INSERT INTO Locations (title, category, address, osm_id, gis_id, raw_description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, category, address, osm_id, gis_id, raw_text))

    conn.commit()
    conn.close()
    print("\nУспех! Тестовый массив сохранен. База database.db готова.")


if __name__ == "__main__":
    main()