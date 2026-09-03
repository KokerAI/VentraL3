# db_config.py (Единый источник кредов для всех скриптов)

# === ТРЕБОВАНИЯ ===
# from db_config import get_db_config
# лучше так импорт: import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent)); from db_config import get_db_config
# pip install python-dotenv psycopg2-binary
# with psycopg2.connect(**get_db_config()) as conn:

import os
from dotenv import load_dotenv, find_dotenv  # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ


def get_db_config():
    """Автонаходит .env из ЛЮБОЙ директории проекта"""
    # Ищем .env начиная с текущей директории и выше до корня
    dotenv_path = find_dotenv()
    if not dotenv_path:
        raise EnvironmentError(
            "❌ Файл .env не найден! Поместите его в корень проекта:\n"
            f"Текущий путь поиска: {os.getcwd()}"
        )
    load_dotenv(dotenv_path)  # Загружаем найденный .env

    required_vars = ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"❌ Отсутствуют переменные в .env: {', '.join(missing)}")

    return {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME'),
        'port': int(os.getenv('DB_PORT', 5432))
    }