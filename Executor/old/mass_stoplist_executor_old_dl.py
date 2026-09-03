import os
import sys
import requests
import psycopg2
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent)); from db_config import get_db_config

# ДОБАВЛЕНИЕ ИСПА В МАССОВЫЙ СТОПЛИСТ В ФОРМАТЕ:  по phone, uuid или executor_id

# === НАСТРОЙКИ ===
exclude_org_ids = [422745070]  # Исключить блокировку по определенным клиентам через запятую или пусто
process_by = 'phone'           # phone id uuid
enable_log = False             # True False
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
auth_file = 'D:/WORK/python/auth.txt'
input_file = 'D:/WORK/python/list_userId.txt'
script_name = os.path.basename(__file__)
db_config = get_db_config()  # Динамическая загрузка из .ENV
# max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)

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

# === ИНИЦИАЛИЗАЦИЯ ===
log_lock = threading.Lock()
console_lock = threading.Lock()
_db_cache = {}
AUTH_TOKEN = None

# === ФУНКЦИИ ===
def load_auth_once(auth_file_path):
    """Загрузка токена один раз"""
    global AUTH_TOKEN
    if AUTH_TOKEN is None:
        with open(auth_file_path) as f:
            AUTH_TOKEN = f.readline().strip()
    return AUTH_TOKEN


def check_db_connection():
    """Проверяет подключение к БД и прерывает выполнение при ошибке"""
    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as e:
        error_msg = str(e).split("FATAL:")[1].strip() if "FATAL:" in str(e) else str(e)
        with console_lock:
            print(f"\n❌ DATABASE_ERROR: {error_msg}\n")
        sys.exit(1)


def get_executor_data(identifier: str, mode: str) -> tuple:
    """Возвращает данные исполнителя"""

    cache_key = (mode, identifier)
    if cache_key in _db_cache:
        return _db_cache[cache_key]

    with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
        if mode == 'phone':
            digits = ''.join(c for c in identifier if c.isdigit())
            search_phone = f"+7{digits[-10:]}" if len(digits) in (10, 11) and digits[-10:].startswith(
                ('9', '8')) else f"+{digits}" if digits else identifier.strip()
            cur.execute("SELECT uuid, phone FROM users WHERE phone = %s", (search_phone,))
        elif mode == 'id':
            cur.execute("SELECT uuid, id FROM users WHERE id = %s", (int(identifier),))
        elif mode == 'uuid' and len(identifier) == 36 and identifier.count('-') == 4:
            cur.execute("SELECT uuid, uuid FROM users WHERE uuid = %s", (identifier,))
        else:
            return None, identifier

        result = cur.fetchone()

    if result and result[0]:
        uuid_val, display_val = result
        if mode == 'phone' and display_val and display_val.startswith('8') and len(display_val) == 11:
            display_val = f"+7{display_val[1:]}"
        _db_cache[cache_key] = (uuid_val, display_val)
        return uuid_val, display_val

    _db_cache[cache_key] = (None, identifier)
    return None, identifier


def get_org_data() -> list:
    """Возвращает данные всех организаций, кроме exclude_org_ids"""
    with psycopg2.connect(**db_config) as conn, conn.cursor() as cur:
        condition = "AND id NOT IN %s" if exclude_org_ids else ""
        query = f"""
            SELECT id, name, org_id 
            FROM organization 
            WHERE org_id IS NOT NULL
              AND org_id ~ '^[a-f0-9]{{8}}-[a-f0-9]{{4}}-4[a-f0-9]{{3}}-[89ab][a-f0-9]{{3}}-[a-f0-9]{{12}}$'
              {condition}
        """
        params = (tuple(exclude_org_ids),) if exclude_org_ids else None
        cur.execute(query, params)
        return cur.fetchall()


def add_executor_to_stoplist(executor_uuid, org_uuid):
    """Добавление исполнителя в стоплист всех организаций, кроме exclude_org_ids"""
    headers = {'accept': '*/*', 'Authorization': AUTH_TOKEN, 'Content-Type': 'application/json'}
    endpoint_url = f'https://{host}/admin/stoplists/{executor_uuid}/'
    r = requests.post(endpoint_url, headers=headers, json=[org_uuid])
    return r.status_code, r.text if r.status_code >= 400 else ""


def process_task(display_value, executor_uuid, org_id, org_name, org_uuid):
    """Обработка задач"""
    if not executor_uuid:
        return display_value, None, None, None, None, "UUID not found", None
    return (*[display_value, executor_uuid, org_id, org_name, org_uuid],
            *add_executor_to_stoplist(executor_uuid, org_uuid))


# === ОСНОВНОЙ КОД ===
try:
    check_db_connection()
    load_auth_once(auth_file)

    with open(input_file, 'r', encoding='utf-8') as f:
        identifiers = [line.strip() for line in f if line.strip()]

    org_data = get_org_data()
    total_pairs = len(identifiers) * len(org_data)
    ok = cnt = 0

    # Открываем лог с автоматической буферизацией по строкам
    log_handle = open(log_file, 'w', encoding='utf-8', buffering=1) if enable_log else None
    if enable_log:
        log_handle.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')

    tasks = []
    for identifier in identifiers:
        executor_uuid, display_value = get_executor_data(identifier, process_by)
        for org_id, org_name, org_uuid in org_data:
            tasks.append((display_value, executor_uuid, org_id, org_name, org_uuid))

    start = datetime.now()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_task, *task) for task in tasks]
        for future in as_completed(futures):
            display_value, executor_uuid, org_id, org_name, org_uuid, status, response = future.result()
            cnt += 1

            with console_lock:
                if status == "UUID not found":
                    msg = f"❌ Executor {display_value} → UUID not found"
                    print(msg)
                else:
                    msg = f"✅ Executor: {display_value}, Org_uuid: {org_uuid}, Org_id: {org_id}, Org_name: {org_name}"
                    print(msg)
                    if 200 <= status <= 299:
                        ok += 1
                    if status < 200 or status > 299:
                        error_msg = f"Error: {response[:200]}"
                        print(error_msg)
                        if enable_log:
                            with log_lock:
                                log_handle.write(error_msg + '\n')

            if enable_log:
                with log_lock:
                    log_handle.write(msg + '\n')

            progress_msg = f"Сделано {cnt} из {total_pairs}."
            with console_lock:
                print(progress_msg)
            if enable_log:
                with log_lock:
                    log_handle.write(progress_msg + '\n')

    # === СТАТИСТИКА ===
    duration = (datetime.now() - start).total_seconds()
    summary = (
        f"\n🔢 Total pairs: {total_pairs}\n"
        f"✅ Success: {ok}\n"
        f"❌ Failed: {total_pairs - ok}\n"
        f"⚡️ Speed: {total_pairs / duration if duration > 0 else 0:.2f} pairs/second\n"
        f"⏱️ Time: {duration:.2f} seconds\n"
    )

    with console_lock:
        print(summary)
    if enable_log:
        with log_lock:
            log_handle.write(summary + '\n')

finally:
    # Гарантированное закрытие лога даже при прерывании
    if enable_log and 'log_handle' in locals() and log_handle:
        try:
            log_handle.close()
        except:
            pass
