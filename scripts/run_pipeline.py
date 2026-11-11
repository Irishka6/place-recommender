import parser
import ai_builder


def main():
    print("=== ЭТАП 1: СБОР ДАННЫХ И ПАРСИНГ ОТЗЫВОВ ===")
    parser.main()

    print("\n=== ЭТАП 2: ИИ-ГЕНЕРАЦИЯ ВЫЖИМОК ЧЕРЕЗ GIGACHAT ===")
    ai_builder.main()

    print("\n=== ОФЛАЙН-ФАЗА ПОДГОТОВКИ БАЗЫ ПОЛНОСТЬЮ ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()