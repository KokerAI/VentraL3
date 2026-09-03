import os
import re
import sys
import time
import requests
import psycopg2
import threading
from threading import Lock
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent));from db_config import get_db_config

# ДОБАВЛЕНИЕ/УДАЛЕНИЕ ИСПА В ЧС ПО БРЕНДАМ ИЗ ФАЙЛОВ:  по phone, uuid или executor_id

# === НАСТРОЙКИ ===
brand_list_status = "Processed"  # Processed Deleted
process_by = 'id'                # phone id uuid
enable_log = False               # True False
host = 'api.dap.ventra.ru'
# host = 'api.stage.dap.ventra.ru'
auth_file = 'D:/WORK/python/auth.txt'
brand_file = 'D:/WORK/python/list_brandId.txt'
user_file = 'D:/WORK/python/list_userId.txt'
script_name = os.path.basename(__file__)
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)
db_config = get_db_config()  # Динамическая загрузка из .ENV

# === БАЗА ДАННЫХ ===
# db_config = {
#     'host': 'prod-dap-db1.msk.ventrago.dev',
#     'port': 5432,
#     # 'host'    = 'stage-db1.msk.ventrago.dev'
#     # 'dbname'    = 'stage'
#     'dbname': 'production',
#     'user': 'user',
#     'password': 'password',
# }

# === ИНИЦИАЛИЗАЦИЯ ===
log_lock = threading.Lock()
brand_cache = {}
brand_cache_lock = threading.Lock()
log_handle = None

# === ЛОГ В ПАПКЕ СКРИПТА ===
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'black_white_brand.log')

def log_msg(msg: str, err: bool = False):
    """Логирует сообщение в консоль и файл"""
    prefix = "❌ " if err else ""
    with log_lock:
        print(f"{prefix}{msg}")
        if enable_log and log_handle is not None:
            log_handle.write(f"{msg}\n")

def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def normalize_phone(phone: str) -> str:
    """Нормализует номер телефона для поиска в БД"""
    digits = ''.join(c for c in phone if c.isdigit())

    if digits.startswith('00') and len(digits) > 2:
        return f'+{digits[2:]}'
    if '+' in phone:
        return f'+{digits}'
    if len(digits) == 11 and digits[0] in '78':
        return f'+7{digits[1:]}'
    if len(digits) == 10 and digits.startswith('9'):
        return f'+7{digits}'
    if len(digits) >= 10:
        return f'+{digits}'
    return phone


def normalize_id(id_str: str) -> str:
    """Удаляет все нецифровые символы из ID"""
    return ''.join(c for c in str(id_str) if c.isdigit())

def is_valid_uuid(uid: str) -> bool:
    """Строгая валидация UUID"""
    if not uid:
        return False
    norm = uid.strip().lower()
    return bool(re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', norm))

def load_brands_to_cache():
    """Загружает все бренды в кэш при старте (1 запрос к БД)"""
    global brand_cache
    retries = 3
    for i in range(retries):
        try:
            with psycopg2.connect(**db_config) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM brands")
                    brand_ids = [str(row[0]) for row in cur.fetchall()]
                    brand_cache = {bid: True for bid in brand_ids}
            log_msg(f"✅ Loaded {len(brand_cache)} brands to cache")
            return
        except Exception as e:
            if i == retries - 1:
                log_msg(f"❌ DB_LOAD_ERROR: {str(e)}", True)
                sys.exit(1)
            time.sleep(1)

def get_brand(brand_id: str) -> bool:
    """Проверяет существование бренда через кэш"""
    with brand_cache_lock:
        return brand_id in brand_cache

def get_user(identifier: str, mode: str) -> tuple[int | None, str]:
    """Получает ID пользователя с retry-логикой"""
    retries = 3
    for i in range(retries):
        try:
            with psycopg2.connect(**db_config) as conn:
                with conn.cursor() as cur:
                    if mode == 'phone':
                        normalized = normalize_phone(identifier)
                        cur.execute("SELECT id FROM users WHERE phone = %s", (normalized,))
                    elif mode == 'id':
                        clean_id = normalize_id(identifier)
                        if not clean_id:
                            return None, identifier
                        cur.execute("SELECT id FROM users WHERE id = %s", (int(clean_id),))
                    elif mode == 'uuid' and is_valid_uuid(identifier):
                        cur.execute("SELECT id FROM users WHERE uuid = %s", (identifier,))
                    else:
                        return None, identifier

                    res = cur.fetchone()
                    return (res[0], identifier) if res else (None, identifier)
        except Exception as e:
            if i == retries - 1:
                log_msg(f"⚠️ DATABASE_ERROR: {str(e)[:100]}", True)
                return None, identifier
            time.sleep(1)

def get_session():
    """Создает сессию requests с retry-логикой"""
    if not hasattr(threading.current_thread(), 'session'):
        session = requests.Session()
        retry_strategy = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["POST"])
        adapter = HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=retry_strategy)
        session.mount('https://', adapter)
        threading.current_thread().session = session
    return threading.current_thread().session

def process_item(task, auth):
    """Обрабатывает пару бренд-идентификатор"""
    brand_id, identifier = task
    brand_id_str = str(brand_id).strip()

    if not get_brand(brand_id_str):
        return brand_id, identifier, None, "NOT_FOUND: Brand not found in cache", None

    user_id, _ = get_user(identifier, process_by)
    if user_id is None:
        return brand_id, identifier, None, "NOT_FOUND: Executor not found", None

    headers = {
        'accept': 'application/hal+json',
        'Content-Type': 'application/json',
        'Authorization': auth
    }
    json_data = {
        "brandId": int(brand_id_str),
        "executorId": user_id,
        "brandListStatus": brand_list_status,
        "startTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    try:
        session = get_session()
        response = session.post(
            f'https://{host}/api/v1/brands/save',
            json=json_data,
            headers=headers,
            timeout=(10, 30)
        )
        return brand_id, identifier, user_id, response.status_code, response.text
    except requests.exceptions.RequestException as e:
        return brand_id, identifier, user_id, "REQUEST_ERROR", str(e)

def read_file_lines(file_path):
    """Читает строки из файла"""
    lines = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
    except FileNotFoundError:
        log_msg(f"❌ FILE_ERROR: File not found: {file_path}", True)
        sys.exit(1)
    return lines

def main():
    """Основная точка входа"""
    global log_handle
    auth = load_auth()
    # Загружаем все бренды в кэш (1 запрос к БД)
    load_brands_to_cache()
    start = datetime.now()

    if enable_log:
        log_handle = open(log_file, 'w', encoding='utf-8')
        log_msg(f'# {script_name}, {start.strftime("%Y-%m-%d %H:%M:%S")}, {brand_list_status}')

    brand_lines = read_file_lines(brand_file)
    identifiers = read_file_lines(user_file)

    if not identifiers:
        log_msg("❌ DATA_ERROR: No valid IDs found in user file", True)
        sys.exit(1)

    tasks = [(brand, ident) for brand in brand_lines for ident in identifiers]
    total = len(tasks)
    cnt, ok = 0, 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_item, task, auth): task for task in tasks}

        for future in as_completed(futures):
            brand, ident, user_id, status, resp = future.result()
            cnt += 1

            # Обработка отображения
            if process_by == 'phone':
                display_ident = normalize_phone(ident)
            elif process_by == 'id':
                display_ident = normalize_id(ident)
            else:
                display_ident = ident

            if isinstance(status, int) and 200 <= status < 300:
                ok += 1
                msg = f"✅ SUCCESS: Brand {brand}, {process_by.capitalize()}: {display_ident}, Executor ID: {user_id}, Status: {status}"
            else:
                if isinstance(status, str) and status.startswith(('NOT_FOUND', 'INVALID', 'REQUEST_ERROR')):
                    error_detail = status.split(':', 1)[-1].strip()
                    msg = f"⚠️ {status.split(':')[0]}: Brand {brand}, {process_by.capitalize()}: {display_ident} [{error_detail}]"
                else:
                    preview = resp[:100] + "..." if resp and len(resp) > 100 else resp
                    msg = f"❌ API_ERROR: Brand {brand}, {process_by.capitalize()}: {display_ident}, Status: {status}, Response: {preview}"

            progress = f"Сделано {cnt} из {total} ({cnt / total:.1%})."
            log_msg(f"{msg}\n{progress}")

    duration = (datetime.now() - start).total_seconds()
    summary = (
        f"\n📊 Total: {total} tasks\n"
        f"✅ Success: {ok}/{total}\n"
        f"❌ Failed: {total - ok}\n"
        f"⏱️ Time: {duration:.1f} sec\n"
        f"⚡️ Speed: {total / max(0.1, duration):.1f} tasks/sec"
    )
    log_msg(summary)

    if enable_log and log_handle:
        log_handle.close()

if __name__ == "__main__":
    main()