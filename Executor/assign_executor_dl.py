import re
import os
import sys
import requests
import threading
import psycopg2
from urllib.parse import quote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent)); from db_config import get_db_config

# НАЗНАЧЕНИЕ ИСПОЛНИТЕЛЕЙ НА ЗАДАНИЯ В ФОРМАТЕ:
# - phone mode: vacancyId|phone   (000000000|79990001122)
# - id mode:    vacancyId|userId  (000000000|123456)

# === НАСТРОЙКИ ===
process_by  = 'phone'  # phone id
enable_log  = True  # True False
host        = 'api.dap.ventra.ru/api'
# host        = 'api.stage.dap.ventra.ru/api'
input_file  = 'D:/WORK/python/list_userId.txt'
auth_file   = 'D:/WORK/python/auth.txt'
_log_lock   = threading.Lock() # Потокобезопасная запись лога
script_name = os.path.basename(__file__)
db_config = get_db_config()  # Динамическая загрузка из .ENV
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
log_file = os.path.join(script_dir, 'assign_executor_dl.log')

# === ЛОГ ПО АБСОЛЮТНОМУ ПУТИ ===
# log_file = 'D:/WORK/python/log.log'
# log_dir = os.path.dirname(log_file)
# if not os.path.exists(log_dir):
#     os.makedirs(log_dir)


# === ФУНКЦИИ ===
def load_auth(auth_file):
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        return f.readline().strip()


def normalize_phone(phone: str) -> str:
    """Очищает телефон до формата 79991112233"""
    digits = ''.join(char for char in phone if char.isdigit())
    return digits[1:] if digits.startswith('8') else digits.lstrip('+')


def get_user_phone_by_id(user_id: str):
    """Получает телефон из БД с валидацией статуса"""
    try:
        # Создаем новое подключение в каждом потоке (psycopg2 не thread-safe)
        with psycopg2.connect(**db_config) as conn:      #🔥.ENV OFF
        # with psycopg2.connect(**get_db_config()) as conn:  #🔥.ENV ON
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT phone, user_status 
                    FROM users 
                    # WHERE id = %s AND user_status = 'ACTIVE'
                    WHERE id = %s
                """, (user_id,))
                result = cur.fetchone()

                if not result:
                    return None, 404, f"User not found or inactive (ID: {user_id})"

                phone, status = result
                return normalize_phone(phone), 200, None

    except Exception as e:
        return None, 500, f"DB error: {str(e)}"


def assign_executor_to_vacancy(vacancyId, phone):
    """Формирует запрос назначения испа на задание"""
    headers = {'Authorization': load_auth(auth_file), 'accept': '*/*'}
    encoded_phone = quote("+" + phone)
    endpoint_url = f'https://{host}/admin/support/assign/vacancy/{vacancyId}?phone={encoded_phone}'
    r = requests.put(endpoint_url, headers=headers)

    return r.status_code, r.text


def process_line(line):
    """Обработка строки с поддержкой разделителей | и }"""
    if not (match := re.match(r'^\s*(\d+)\s*[\|}]\s*([\w\+]+)\s*$', line.strip())):
        return None, None, 400, f"Invalid format: '{line}'. Use 'vacancyId|identifier'"

    vacancy_id, identifier = match.groups()

    if process_by == 'id':
        if not identifier.isdigit():
            return vacancy_id, identifier, 400, "Invalid user ID format"
        phone, status, error = get_user_phone_by_id(identifier)
        if error:
            return vacancy_id, identifier, status, error
        identifier = phone
    else:
        identifier = normalize_phone(identifier)
        if len(identifier) != 11 or not identifier.isdigit():
            return vacancy_id, identifier, 400, f"Invalid phone after normalization: '{identifier}'"

    return vacancy_id, identifier, *assign_executor_to_vacancy(vacancy_id, identifier)


# === ЧТЕНИЕ ===
with open(input_file, 'r', encoding='utf-8') as c:
    lines = [line.strip() for line in c if line.strip()]

total = len(lines)
cnt, ok = 0, 0

# Открываем лог если enable_log = True
if enable_log:
    log_handle = open(log_file, 'w', encoding='utf-8')
    log_handle.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
else:
    log_handle = None

# === МНОГОПОТОЧНАЯ ОБРАБОТКА ===
start = datetime.now()
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(process_line, line): line for line in lines}
    for future in as_completed(futures):
        vacancyId, identifier, status, response = future.result()
        # Лок каунтеров:
        with _log_lock:
            cnt += 1
            if 200 <= status < 300: ok += 1

        icon = "✅" if 200 <= status < 300 else "❌"
        context = 'UserId' if process_by == 'id' else 'Phone'
        msg = f"{icon} VacancyId: {vacancyId}, {context}: {identifier}, Status: {status}, Response: {response}"
        progress = f"Сделано {cnt} из {total}."

        # Лок вывода:
        with _log_lock:
            print(msg)
            print(progress)
            if enable_log and log_handle:
                log_handle.write(msg + '\n')
                log_handle.write(progress + '\n')

# === СТАТИСТИКА ===
duration = (datetime.now() - start).total_seconds()
summary = (
    f"\n✅ Completed: {ok}/{total} assignations in {duration:.2f} seconds"
    f"\n❌ Failed: {total - ok}/{total}"
    f"\n⚡️ Speed: {total / duration:.1f} req/sec" if duration > 0 else ""
)

# === ПРОГРЕСС-БАР ===
progress = int((ok / total) * 30) if total > 0 else 0
bar = "█" * progress + "░" * (30 - progress)
progress_percent = (ok / total * 100) if total > 0 else 0
progress_bar_str = f"\n📈 Progress: [{bar}] {ok}/{total} ({progress_percent:.1f}%)"

# Блокировка для финального вывода
with _log_lock:
    final_output = summary + progress_bar_str
    print(final_output)
    if enable_log and log_handle:
        log_handle.write(final_output + '\n')

# Закрытие файла под блокировкой
if enable_log and log_handle:
    log_handle.close()