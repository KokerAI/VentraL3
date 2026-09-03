import os
import sys
import requests
import psycopg2
import threading
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent)); from db_config import get_db_config

# ДОБАВЛЕНИЕ/УДАЛЕНИЕ ИСПА В СТОПЛИСТ КЛИЕНТОВ:  по phone, uuid или executor_id

# === НАСТРОЙКИ ===
brand_list_status = "Processed"  # Processed Deleted
process_by = 'id'   # phone id uuid
enable_log = False     # True False
token_refresh_interval = 20000  # Обновлять токен каждые N запросов
host = 'api.dap.ventra.ru'
# host = 'api.stage.dap.ventra.ru'
auth_file = 'D:/WORK/python/auth.txt'
brand_file = 'D:/WORK/python/list_brandId.txt'
user_file = 'D:/WORK/python/list_userId.txt'
script_name = os.path.basename(__file__)
max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
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

# === ЛОГ В ПАПКЕ СКРИПТА ===
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'black_white_brand.log')

# === ЛОГ ПО АБСОЛЮТНОМУ ПУТИ ===
# log_file = 'D:/WORK/python/log.log'
# log_dir = os.path.dirname(log_file)
# if not os.path.exists(log_dir):
#     os.makedirs(log_dir)

# === ИНИЦИАЛИЗАЦИЯ ===
_db_cache = {}
_token_cache = None
_token_requests_count = 0
_token_lock = threading.Lock()
_session_cache = {}


# === ФУНКЦИИ ===
def get_session():
    """Получает сессию requests с кэшированием по потокам"""
    thread_id = threading.get_ident()
    if thread_id not in _session_cache:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=3)
        session.mount('https://', adapter)
        _session_cache[thread_id] = session
    return _session_cache[thread_id]


def check_db_connection():
    """Проверяет подключение к БД и возвращает результат"""
    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as e:
        error_text = str(e)
        error_msg = error_text.split("FATAL:")[1].strip() if "FATAL:" in error_text else error_text
        print(f"\n❌ DATABASE_ERROR: {error_msg}\n")
        sys.exit(1)


# === ФУНКЦИИ ===
def load_auth(auth_file_path):
    """Загружает токен с кэшированием"""
    global _token_cache, _token_requests_count
    with _token_lock:
        _token_requests_count += 1
        if _token_cache is None or _token_requests_count % token_refresh_interval == 1:
            try:
                with open(auth_file_path) as f:
                    _token_cache = f.readline().strip()
            except FileNotFoundError:
                print(f"❌ AUTH_ERROR: Auth file not found: {auth_file_path}")
                sys.exit(1)
            except Exception as e:
                print(f"❌ AUTH_ERROR: Failed to read auth file: {e}")
                sys.exit(1)
    return _token_cache


def db_get(table, field, value, return_field='id'):
    """Получает значение из БД с кэшированием"""
    cache_key = f"{table}_{field}_{value}_{return_field}"
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    try:
        with psycopg2.connect(**db_config) as conn:

            with conn.cursor() as cur:
                cur.execute(f"SELECT {return_field} FROM {table} WHERE {field} = %s", (value,))
                result = cur.fetchone()
        value = result[0] if result else None
        _db_cache[cache_key] = value
        return value
    except Exception as e:
        print(f"⚠️ DATABASE_ERROR: {e}")
        return None


def get_executor(identifier):
    """Получает ID исполнителя в зависимости от режима"""
    if process_by == 'id':
        if not identifier.isdigit():
            return None, "INVALID: ID must be numeric"
        executor_id = int(identifier)
        return executor_id if db_get('users', 'id', executor_id) else None, None

    elif process_by == 'phone':
        phone = str(identifier).strip()
        search_phone = '+' + phone if phone.isdigit() and len(phone) == 11 and phone.startswith('7') else phone
        return db_get('users', 'phone', search_phone), None

    elif process_by == 'uuid':
        if len(identifier) == 36 and identifier.count('-') == 4:
            return db_get('users', 'uuid', identifier), None
        return None, "INVALID: Invalid UUID format"

    return None, "INVALID: Invalid process_by mode"


def process_item(brand_id, identifier):
    """Обрабатывает пару бренд-идентификатор"""
    # Проверка корректности brand_id
    try:
        brand_id_int = int(brand_id)
    except (ValueError, TypeError):
        return brand_id, identifier, None, "INVALID: Brand ID must be numeric", None

    # Проверка существования бренда
    if not db_get('brands', 'id', brand_id_int):
        return brand_id, identifier, None, "NOT_FOUND: Brand not found in database", None

    # Получение и проверка исполнителя
    executor_id, error = get_executor(identifier)
    if error:
        return brand_id, identifier, None, error, None
    if executor_id is None:
        return brand_id, identifier, None, "NOT_FOUND: Executor not found", None
    if not db_get('users', 'id', executor_id):
        return brand_id, identifier, None, "NOT_FOUND: Executor ID not found in database", None

    # Формирование и отправка запроса
    headers = {
        'accept': 'application/hal+json',
        'Content-Type': 'application/json',
        'Authorization': load_auth(auth_file)
    }
    json_data = {
        "brandId": brand_id_int,
        "executorId": executor_id,
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
        return brand_id, identifier, executor_id, response.status_code, response.text
    except requests.exceptions.Timeout:
        return brand_id, identifier, executor_id, "REQUEST_ERROR", "Timeout during request"
    except requests.exceptions.ConnectionError:
        return brand_id, identifier, executor_id, "REQUEST_ERROR", "Connection error"
    except Exception as e:
        return brand_id, identifier, executor_id, "REQUEST_ERROR", str(e)


def read_file_lines(file_path, validator_func=None):
    """Читает строки из файла с опциональной валидацией"""
    lines = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and (validator_func is None or validator_func(line)):
                    lines.append(line)
    except FileNotFoundError:
        print(f"❌ FILE_ERROR: File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ FILE_ERROR: Failed to read {file_path}: {e}")
        sys.exit(1)
    return lines


def format_output(status, brand_id, identifier, executor_id, response, cnt, total):
    """Формирует сообщение для вывода в зависимости от статуса"""
    # === Безопасная проверка числового статуса ===
    if isinstance(status, str) and status.startswith(('NOT_FOUND', 'INVALID', 'REQUEST_ERROR')):
        msg = f"⚠️ {status}: Brand {brand_id}, {process_by.capitalize()}: {identifier}"
    elif isinstance(status, int) and 200 <= status < 300:
        msg = f"✅ SUCCESS: Brand {brand_id}, {process_by.capitalize()}: {identifier}, Executor: {executor_id}, Status: {status}"
    else:
        # Для числовых статусов > 300 или других строковых ошибок
        if isinstance(status, int):
            response_preview = response[:100] + "..." if len(response) > 100 else response
            msg = f"❌ API_ERROR: Brand {brand_id}, {process_by.capitalize()}: {identifier}, Status: {status}, Response: {response_preview}"
        else:
            # Если status - строка, но не одна из известных ошибок
            response_preview = response[:100] + "..." if response and len(str(response)) > 100 else str(
                response) if response else "Unknown error"
            msg = f"❌ API_ERROR: Brand {brand_id}, {process_by.capitalize()}: {identifier}, Status: {status}, Response: {response_preview}"

    return [
        msg,
        f"Сделано {cnt} из {total}."
    ]


def write_log(messages, log_file_path):
    """Записывает сообщения в лог-файл"""
    if enable_log:
        try:
            with open(log_file_path, 'a', encoding='utf-8') as log:
                for msg in messages:
                    log.write(msg + '\n')
        except Exception as e:
            print(f"⚠️ LOG_ERROR: Failed to write to log: {e}")


# === ОСНОВНОЙ КОД ===
check_db_connection()
all_brand_lines = []
try:
    with open(brand_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:  # Добавляем ВСЕ непустые строки
                all_brand_lines.append(line)
except FileNotFoundError:
    print(f"❌ FILE_ERROR: Brand file not found: {brand_file}")
    sys.exit(1)
except Exception as e:
    print(f"❌ FILE_ERROR: Failed to read brand file: {e}")
    sys.exit(1)

identifiers = read_file_lines(user_file)

if not identifiers:  # Проверяем только наличие идентификаторов
    print("❌ DATA_ERROR: No valid IDs found in user file")
    sys.exit(1)

total = len(all_brand_lines) * len(identifiers)
cnt, ok = 0, 0

# Подготовка лог-файла
if enable_log:
    log_handle = open(log_file, 'w', encoding='utf-8')
    log_handle.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, {brand_list_status}\n\n')
else:
    log_handle = None

start = datetime.now()
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Обрабатываем ВСЕ строки из файла брендов
    futures = [executor.submit(process_item, b, i) for b in all_brand_lines for i in identifiers]

    for future in as_completed(futures):
        brand, ident, eid, status, resp = future.result()
        cnt += 1

        if isinstance(status, int) and 200 <= status < 300:
            ok += 1

        # Формируем и выводим сообщения
        messages = format_output(status, brand, ident, eid, resp, cnt, total)
        for msg in messages:
            print(msg)
        write_log(messages, log_file)

# === ИТОГОВАЯ СТАТИСТИКА ===
duration = (datetime.now() - start).total_seconds()
summary = (
    f"\n📊 Total: {len(identifiers)} executors, {len(all_brand_lines)} brands. Total pairs: {total}\n"
    f"✅ Success: {ok}/{total}\n"
    f"❌ Failed: {total - ok}/{total}\n"
    f"⏱️ Time: {duration:.2f} seconds\n"
    f"⚡️ Speed: {total / duration:.2f} projects/sec" if duration > 0 else "⚡ Speed: N/A")

if duration > 0 and ok > 0:
    summary += f"\n📈 Network: {ok / duration:.1f} requests/sec"

print(summary)
if enable_log:
    write_log([summary], log_file)