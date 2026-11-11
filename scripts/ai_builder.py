import os
import sqlite3
import requests
import uuid
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Ваши "Авторизационные данные" GigaChat
GIGACHAT_CREDENTIALS = "MDFhMWJmZjItOWRjNi03NzM4LTk0OTYtOTQwZDcyZDQ3MjBmOjMxZWZkNDY2LTI0MDAtNDA3Mi05MzkxLTQ5YjQ3MzIxNDBhYQ=="


def get_access_token():
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {GIGACHAT_CREDENTIALS}'
    }
    try:
        response = requests.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=False)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Ошибка получения токена: {response.text}")
            return None
    except Exception as e:
        print(f"Системная ошибка авторизации: {e}")
        return None


def generate_ai_data(combined_text, token):
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    # Теперь никакого JSON. Просим обычный текст и теги в конце.
    system_prompt = """Ты — профессиональный гид-аналитик. Твоя задача — внимательно изучить сырое описание места и отзывы посетителей.
    1. На их основе составь информативную и объективную выжимку (около 5-6 предложений).
    2. В САМОМ КОНЦЕ текста ОБЯЗАТЕЛЬНО напиши от 2 до 5 хэштегов, отражающих атмосферу (например: #тишина #искусство #вкусный_кофе).
    Пиши обычным текстом, БЕЗ формата JSON."""

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system_prompt},
            # ИИ получает и сырое описание (2GIS), и живые комментарии (Selenium)
            {"role": "user", "content": f"Справочные данные и отзывы:\n{combined_text}"}
        ],
        "temperature": 0.25
    }

    try:
        response = requests.post(url, headers=headers, json=payload, verify=False)
        response.encoding = 'utf-8'

        if response.status_code == 200:
            raw_text = response.json()['choices'][0]['message']['content'].strip()

            # Python сам находит все слова, начинающиеся с #, переводит в нижний регистр и убирает дубли
            tags = list(set([t.lower() for t in re.findall(r'#\w+', raw_text)]))

            # Убираем хэштеги из основного текста, чтобы они не дублировались в карточке
            summary = re.sub(r'#\w+', '', raw_text).strip()

            return {"summary": summary, "tags": tags}
        else:
            print(f"Ошибка API GigaChat: {response.status_code}")
            return None
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return None


def main():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, 'data', 'database.db')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Берем локации, сырое описание из 2GIS и спарсенные комменты
    cursor.execute("SELECT id, title, raw_description, comments FROM Locations WHERE ai_summary IS NULL")
    rows = cursor.fetchall()

    if not rows:
        print("Все локации уже обработаны!")
        conn.close()
        return

    print(f"Найдено локаций для ИИ-обработки: {len(rows)}")
    token = get_access_token()

    if not token:
        print("Ошибка токена. Проверьте GIGACHAT_CREDENTIALS.")
        conn.close()
        return

    for row_id, title, raw_desc, comments in rows:
        print(f"Анализ: {title}...")

        # Склеиваем описание и отзывы для отправки в ИИ
        combined_text = f"ОПИСАНИЕ:\n{raw_desc}\n\nОТЗЫВЫ ПОСЕТИТЕЛЕЙ:\n{comments}"

        ai_result = generate_ai_data(combined_text, token)

        if ai_result:
            summary = ai_result.get("summary", "")
            tags = ai_result.get("tags", [])

            # 1. Сохраняем текстовую выжимку в базу мест
            cursor.execute("UPDATE Locations SET ai_summary = ? WHERE id = ?", (summary, row_id))

            # 2. Сохраняем сгенерированные хэштеги в связанные таблицы
            for tag in tags:
                # Добавляем тег в уникальный список тегов
                cursor.execute("INSERT OR IGNORE INTO Tags (name) VALUES (?)", (tag,))

                # Достаем его ID
                cursor.execute("SELECT id FROM Tags WHERE name = ?", (tag,))
                tag_id_row = cursor.fetchone()
                if tag_id_row:
                    tag_id = tag_id_row[0]
                    # Привязываем тег к локации
                    cursor.execute("INSERT OR IGNORE INTO Location_Tags (location_id, tag_id) VALUES (?, ?)",
                                   (row_id, tag_id))

            conn.commit()
            print(f"  + Успешно (Теги: {', '.join(tags)})")
        else:
            print("  - Ошибка генерации. Пропуск.")

    conn.close()
    print("ИИ-обработка завершена. Теги и описания добавлены в БД!")


if __name__ == "__main__":
    main()