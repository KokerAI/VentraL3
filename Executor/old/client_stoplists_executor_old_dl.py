import os
import sys
import requests
import psycopg2
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent)); from db_config import get_db_config

# ДОБАВЛЕНИЕ ИСПА В МАССОВЫЙ СТОПЛИСТ В ФОРМАТЕ:  по phone, uuid или executor_id

# === НАСТРОЙКИ ===
exclude_org_ids = [422745070]  # Исключить блокировку по определенным клиентам через запятую или пусто
process_by = 'phone'           # phone id uuid
enable_log = True              # True False
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
auth_file = 'D:/WORK/python/auth.txt'
input_file = 'D:/WORK/python/list_userId.txt'
script_name = os.path.basename(__file__)
db_config = get_db_config()  # Динамическая загрузка из .ENV
max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
# max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)

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
log_file = os.path.join(script_dir, 'client_stoplist_executor.log')

# === ЛОГ ПО АБСОЛЮТНОМУ ПУТИ ===
# log_file = 'D:/WORK/python/log.log'
# log_dir = os.path.dirname(log_file)
# if not os.path.exists(log_dir):
#     os.makedirs(log_dir)

# === ГЛОБАЛЬНЫЙ КЭШ ===
_db_cache = {}

# === ФУНКЦИИ ===
def load_auth(auth_file):
    with open(auth_file) as f:
        return f.readline().strip()


def check_db_connection():
    """Проверяет подключение к БД и прерывает выполнение при ошибке"""
    try:
        conn = psycopg2.connect(**db_config)
        conn.close()
        return True
    except Exception as e:
        error_text = str(e)
        error_msg = error_text.split("FATAL:")[1].strip() if "FATAL:" in error_text else error_text
        print(f"\n❌ DATABASE_ERROR: {error_msg}\n")
              # f"Host: {db_config['host']}, User: {db_config['user']}\n")
        sys.exit(1)


def get_executor_uuid_by_phone(phone):
    # Используем глобальный кэш
    cache_key = ('get_executor_uuid_by_phone', phone)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) in (10, 11) and digits[-10].startswith(('9', '8')):
        search_phone = f"+7{digits[-10:]}"  # 10 цифр после +7
    else:
        search_phone = f"+{digits}" if digits else phone.strip()

    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    cur.execute("SELECT uuid FROM users WHERE phone = %s", (search_phone,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    # Сохраняем результат в кэш (даже если None)
    uuid = result[0] if result else None
    _db_cache[cache_key] = uuid
    return uuid


def get_executor_uuid_by_id(executor_id):
    # Используем глобальный кэш
    cache_key = ('get_executor_uuid_by_id', executor_id)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    cur.execute("SELECT uuid FROM users WHERE id = %s", (int(executor_id),))
    result = cur.fetchone()
    cur.close()
    conn.close()

    # Сохраняем результат в кэш (даже если None)
    uuid = result[0] if result else None
    _db_cache[cache_key] = uuid
    return uuid


def get_org_uuids():
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    if exclude_org_ids:
        query = """
            SELECT org_id FROM organization 
            WHERE org_id IS NOT NULL 
              AND id NOT IN %s
              AND org_id ~ '^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$'
        """
        cur.execute(query, (tuple(exclude_org_ids),))
    else:
        cur.execute("""
            SELECT org_id FROM organization 
            WHERE org_id IS NOT NULL 
              AND org_id ~ '^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$'
        """)
    result = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return result


def add_executor_to_stoplist(executor_uuid, org_uuid):
    headers = {'accept': '*/*', 'Authorization': load_auth(auth_file), 'Content-Type': 'application/json'}
    json_data = [org_uuid]
    endpoint_url = f'https://{host}/admin/stoplists/{executor_uuid}/'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


def process_task(identifier, executor_uuid, org_uuid):
    """Обёртка для отправки одного запроса"""
    if not executor_uuid:
        return identifier, None, None, "UUID not found", None
    status, response = add_executor_to_stoplist(executor_uuid, org_uuid)
    return identifier, executor_uuid, org_uuid, status, response


# === ЧТЕНИЕ И ОБРАБОТКА ===
check_db_connection()
with open(input_file, 'r', encoding='utf-8') as f:
    identifiers = [line.strip() for line in f if line.strip()]

org_uuids = get_org_uuids()
total_pairs = len(identifiers) * len(org_uuids)
ok = 0
cnt = 0

if enable_log:
    log_handle = open(log_file, 'w', encoding='utf-8')
    log_handle.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
else:
    log_handle = None

tasks = []
for identifier in identifiers:
    if process_by == 'phone':
        executor_uuid = get_executor_uuid_by_phone(identifier)
    elif process_by == 'id':
        executor_uuid = get_executor_uuid_by_id(identifier)
    elif process_by == 'uuid':
        # Проверяем, что строка выглядит как UUID
        if len(identifier) == 36 and identifier.count('-') == 4:
            executor_uuid = identifier
        else:
            executor_uuid = None
    else:
        executor_uuid = None

    for org_uuid in org_uuids:
        tasks.append((identifier, executor_uuid, org_uuid))

# === МНОГОПОТОЧНОСТЬ ===
start = datetime.now()
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [
        executor.submit(process_task, ident, eu, ou)
        for ident, eu, ou in tasks
    ]

    for future in as_completed(futures):
        identifier, executor_uuid, org_uuid, status, response = future.result()
        cnt += 1

        if status == "UUID not found":
            msg = f"❌ Executor {identifier} → UUID not found"
            print(msg)
            if enable_log:
                log_handle.write(msg + '\n')
        else:
            msg = f"✅ Executor: {identifier}, Org: {org_uuid}, Status: {status}"
            print(msg)
            if 200 <= status <= 299:
                ok += 1
            if enable_log:
                log_handle.write(msg + '\n')

            if not (200 <= status <= 299):
                error_msg = f"Error: {response}"
                print(error_msg)
                if enable_log:
                    log_handle.write(error_msg + '\n')

        print(f"Сделано {cnt} из {total_pairs}.")

# === ИТОГОВАЯ СТАТИСТИКА ===
duration = (datetime.now() - start).total_seconds()
speed = total_pairs / duration if duration > 0 else 0

summary = (

    f"\n🔢 Total pairs: {total_pairs}\n"
    f"✅ Success: {ok}\n"
    f"❌ Failed: {total_pairs - ok}\n"
    f"⚡️ Speed: {speed:.2f} pairs/second\n"
    f"⏱️ Time: {duration:.2f} seconds\n"
)

print(summary)
if enable_log:
    log_handle.write(summary + '\n')
    log_handle.close()