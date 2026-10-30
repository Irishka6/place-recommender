import sqlite3
import requests
import json

# Настройки локальной LLM Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
# Укажите здесь модель, которую скачали в Ollama (например, llama3 или saiga-llama3)
MODEL_NAME = "llama3"


def generate_summary(raw_text):
    # Промпт, который мы спроектировали на этапе архитектуры
    prompt = f"""Ты — современный локальный гид по Москве. Твоя задача — прочитать сырые данные о локации и составить короткую, объективную выжимку (максимум 3 предложения).
    Выдели главную фишку места и укажи минус, если он есть. Пиши живым языком без рекламных штампов.

    Сырые данные:
    {raw_text}
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            print(f"Ошибка API Ollama: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        print("Ошибка: Ollama не запущена. Проверьте, что приложение работает (http://localhost:11434).")
        return None
    except Exception as e:
        print(f"Произошла ошибка при обращении к ИИ: {e}")
        return None


def main():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Выбираем только те локации, где выжимка еще не создана
    cursor.execute("SELECT id, title, raw_description FROM Locations WHERE ai_summary IS NULL")
    rows = cursor.fetchall()

    if not rows:
        print("Все локации уже обработаны!")
        conn.close()
        return

    print(f"Найдено локаций для обработки ИИ: {len(rows)}\n")

    for row_id, title, raw_desc in rows:
        print(f"Генерация выжимки для: {title}...")

        summary = generate_summary(raw_desc)

        if summary:
            # Обновляем запись в базе данных
            cursor.execute("UPDATE Locations SET ai_summary = ? WHERE id = ?", (summary, row_id))
            conn.commit()
            print(f"Итог: {summary}\n")
        else:
            print("Пропуск локации из-за ошибки генерации.\n")
            break  # Прерываем цикл, если Ollama недоступна

    conn.close()
    print("Офлайн-генерация выжимок завершена. База готова к работе с сервером FastAPI.")


if __name__ == "__main__":
    main()