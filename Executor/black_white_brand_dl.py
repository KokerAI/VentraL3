import os
import sys
import json
import requests
import psycopg2
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent)); from db_config import get_db_config

# РАБОТА С ЧЕРНЫМ/БЕЛЫМ СПИСКОМ ПО БРЕНДАМ В ФОРМАТЕ:
# - phone mode: brandId|phone   (000000000|79990001122)
# - id mode:    brandId|userId  (000000000|123456)
# - uuid mode:  brandId|uuid    (000000000|85bcf826-a4da-4bef-99fb-faa25701ce4c)

# === НАСТРОЙКИ ===
brand_list_status = 'Deleted'    # Processed Deleted
process_by = 'phone'             # phone id uuid
enable_log = False               # True False
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
auth_file = 'D:/WORK/python/auth.txt'
input_file = 'D:/WORK/python/list_brandId.txt'
script_name = os.path.basename(__file__)
db_config = get_db_config()  # Динамическая загрузка из .ENV
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию

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

# === ЛОГ В ПАПКЕ СКРИПТА ===
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'black_white_brand.log')

# === ЛОГ ПО АБСОЛЮТНОМУ ПУТИ ===
# log_file = 'D:/WORK/python/log.log'
# log_dir = os.path.dirname(log_file)
# if not os.path.exists(log_dir):
#     os.makedirs(log_dir)

# === ГЛОБАЛЬНЫЙ КЭШ ===
_db_cache = {}


# === ФУНКЦИИ ===
def load_auth(auth_file):
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        return f.readline().strip()


def check_db_connection():
    """Проверяет подключение к БД и прерывает выполнение при ошибке"""
    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as e:
        error_text = str(e)
        error_msg = error_text.split("FATAL:")[1].strip() if "FATAL:" in error_text else error_text
        print(f"\n❌ DATABASE_ERROR: {error_msg}\n")
        sys.exit(1)


def brand_exists(brand_id):
    """Проверяет существование бренда в БД с кэшированием"""
    cache_key = ('brand_exists', brand_id)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM brands WHERE id = %s", (brand_id,))
            exists = cur.fetchone() is not None
            _db_cache[cache_key] = exists
            return exists
    except Exception as e:
        print(f"⚠️ DATABASE_ERROR: {e}")
        return False


def get_executor_id_by_uuid(executor_uuid):
    """Получает ID исполнителя по UUID с кэшированием"""
    cache_key = ('get_executor_id_by_uuid', executor_uuid)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE uuid = %s", (executor_uuid,))
            result = cur.fetchone()
            executor_id = result[0] if result else None
            _db_cache[cache_key] = executor_id
            return executor_id
    except Exception as e:
        print(f"⚠️ DATABASE_ERROR: {e}")
        return None


def get_uuid_by_executor_id(executor_id):
    """Получает UUID по ID исполнителя с кэшированием"""
    cache_key = ('get_uuid_by_executor_id', executor_id)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT uuid FROM users WHERE id = %s", (executor_id,))
            result = cur.fetchone()
            uuid = result[0] if result else None
            _db_cache[cache_key] = uuid
            return uuid
    except Exception as e:
        print(f"⚠️ DATABASE_ERROR: {e}")
        return None


def get_uuid_by_phone(phone):
    """Получает UUID по телефону с кэшированием"""
    cache_key = ('get_uuid_by_phone', phone)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    phone = str(phone).strip()
    search_phone = '+' + phone if phone.isdigit() and len(phone) == 11 and phone.startswith('7') else phone

    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT uuid FROM users WHERE phone = %s", (search_phone,))
            result = cur.fetchone()
            uuid = result[0] if result else None
            _db_cache[cache_key] = uuid
            return uuid
    except Exception as e:
        print(f"⚠️ DATABASE_ERROR: {e}")
        return None


def get_uuid_by_uuid(executor_uuid):
    """Валидирует и возвращает UUID"""
    if len(executor_uuid) == 36 and executor_uuid.count('-') == 4:
        return executor_uuid
    return None


def update_brand_blacklist(brand_id, executor_uuid):
    """Обновляет статус исполнителя в черном списке бренда"""
    auth_token = load_auth(auth_file)
    headers = {
        'Authorization': auth_token,
        'accept': 'application/hal+json',
        'Content-Type': 'application/json'
    }

    # Получаем executor_id по UUID
    executor_id = get_executor_id_by_uuid(executor_uuid)
    if not executor_id:
        return 404, "Executor ID not found for UUID"

    # Текущее время в формате ISO 8601 UTC
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "brandId": int(brand_id),
        "executorId": int(executor_id),
        "brandListStatus": brand_list_status,
        "startTime": current_time
    }

    endpoint_url = f'https://{host}/v1/brands/save'
    try:
        r = requests.post(endpoint_url, headers=headers, json=payload, timeout=10)
        return r.status_code, r.text
    except requests.exceptions.RequestException as e:
        return "REQUEST_ERROR", f"Network error: {str(e)}"


def process_line(line):
    """Обрабатывает одну строку из файла"""
    try:
        brand_id, identifier = [part.strip() for part in line.split("|")]

        # Проверка существования бренда
        if not brand_exists(brand_id):
            return brand_id, identifier, None, "NOT_FOUND: Brand not found in database", None

        # Получаем UUID в зависимости от режима
        if process_by == 'id':
            executor_uuid = get_uuid_by_executor_id(int(identifier))
        elif process_by == 'phone':
            executor_uuid = get_uuid_by_phone(identifier)
        elif process_by == 'uuid':
            executor_uuid = get_uuid_by_uuid(identifier)
        else:
            return brand_id, identifier, None, "INVALID: Invalid process_by mode", None

        if not executor_uuid:
            return brand_id, identifier, None, "NOT_FOUND: UUID not found", None

        status, response = update_brand_blacklist(brand_id, executor_uuid)
        return brand_id, identifier, executor_uuid, status, response
    except Exception as e:
        return line, None, None, "REQUEST_ERROR", f"Processing error: {str(e)}"


# === ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БД ===
check_db_connection()

# === ЧТЕНИЕ И ОБРАБОТКА ===
with open(input_file, 'r', encoding='utf-8') as c:
    lines = [line.strip() for line in c if line.strip()]

total = len(lines)
cnt = 0
ok = 0

# Открываем лог если enable_log = True
if enable_log:
    log_handle = open(log_file, 'w', encoding='utf-8')
    log_handle.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, {brand_list_status}\n\n')
else:
    log_handle = None

# === МНОГОПОТОЧНАЯ ОБРАБОТКА ===
start = datetime.now()
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_line, line) for line in lines]

    for future in as_completed(futures):
        brand_id, identifier, executor_uuid, status, response = future.result()
        cnt += 1

        # Формирование сообщения в зависимости от статуса
        action = "ADD_TO_BLACKLIST" if brand_list_status == "Processed" else "REMOVE_FROM_BLACKLIST"

        if isinstance(status, str) and status.startswith(('NOT_FOUND', 'INVALID', 'REQUEST_ERROR')):
            msg = f"⚠️ {status}: Brand {brand_id}, {process_by.capitalize()}: {identifier}, Action: {action}"
        elif 200 <= status < 300:
            msg = f"✅ SUCCESS: Brand {brand_id}, {process_by.capitalize()}: {identifier}, Executor UUID: {executor_uuid}, Status: {status}, Action: {action}"
            ok += 1
        else:
            response_preview = response[:100] + "..." if len(response) > 100 else response
            msg = f"❌ API_ERROR: Brand {brand_id}, {process_by.capitalize()}: {identifier}, Status: {status}, Response: {response_preview}, Action: {action}"

        # Вывод и логирование
        print(msg)
        if enable_log:
            log_handle.write(msg + '\n')

        progress_msg = f"Сделано {cnt} из {total}."
        print(progress_msg)
        if enable_log:
            log_handle.write(progress_msg + '\n')

# === ИТОГОВАЯ СТАТИСТИКА ===
duration = (datetime.now() - start).total_seconds()
summary = (
    f"\n📊 Total: {total} brand-executor pairs\n"
    f"✅ Success: {ok} pairs processed\n"
    f"❌ Failed: {total - ok} pairs failed\n"
    f"⏱️ Time: {duration:.2f} seconds\n"
    f"⚡️ Speed: {total / duration:.2f} requests/sec" if duration > 0 else "⚡ Speed: N/A"
)

if duration > 0 and ok > 0:
    summary += f"\n📈 Network: {ok / duration:.1f} requests/sec"

# === ПРОГРЕСС-БАР ===
progress = int((ok / total) * 30) if total > 0 else 0
bar = "█" * progress + "░" * (30 - progress)
progress_percent = (ok / total * 100) if total > 0 else 0
progress_bar_str = f"📈 Progress: [{bar}] {ok}/{total} ({progress_percent:.1f}%)"

full_output = summary + "\n" + progress_bar_str
print(full_output)

# Запись в лог
if enable_log:
    log_handle.write(full_output + '\n')
    log_handle.close()