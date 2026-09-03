import os
import sys
import requests
import threading
from urllib.parse import quote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Назначение исполнителя на задание в формате: vacancyId|phone   000000000|79990001122

# === ОСНОВНЫЕ НАСТРОЙКИ ===
enable_log = True  # True False
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
input_file = 'D:/WORK/python/list_userId.txt'
auth_file = 'D:/WORK/python/auth.txt'
_log_lock = threading.Lock() # Потокобезопасная запись лога
script_name = os.path.basename(__file__)
max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
# max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)

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


def assign_executor_to_vacancy(vacancyId, phone):
    """Формирует запрос назначения испа на задание"""
    headers = {'Authorization': load_auth(auth_file), 'accept': '*/*'}
    encoded_phone = quote("+" + phone)
    endpoint_url = f'https://{host}/admin/support/assign/vacancy/{vacancyId}?phone={encoded_phone}'
    r = requests.put(endpoint_url, headers=headers)

    return r.status_code, r.text


def process_line(line):
    """Обработка строк в файле"""
    vacancyId, phone = [part.strip() for part in line.strip().split("|")]
    status, response = assign_executor_to_vacancy(vacancyId, phone)
    return vacancyId, phone, status, response


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
        vacancyId, phone, status, response = future.result()
        # Лок каунтеров:
        with _log_lock:
            cnt += 1
            if 200 <= status < 300: ok += 1

        icon = "✅" if 200 <= status < 300 else "❌"
        msg = f"{icon} VacancyId: {vacancyId}, Phone: {phone}, Status: {status}, Response: {response}"
        progress = f"Сделано {cnt} из {total}."

        # Лок вывода:
        with _log_lock:
            print(msg)
            print(progress)
            if enable_log and log_handle:
                log_handle.write(msg + '\n')
                log_handle.write(progress + '\n')

duration = (datetime.now() - start).total_seconds()
summary = (
    f"\n✅ Completed: {ok}/{total} assignations in {duration:.2f} seconds"
    f"\n❌ Failed: {total - ok}/{total}"
    f"\n📈 Speed: {total / duration:.1f} req/sec" if duration > 0 else ""
)

# Блокировка для финального вывода
with _log_lock:
    print(summary)
    if enable_log and log_handle:
        log_handle.write(summary + '\n')

# Закрытие файла под блокировкой
if enable_log and log_handle:
        log_handle.close()

'''
for line in lines:
    cnt += 1
    vacancyId, phone = line.strip().split("|")
    status, response = assign_executor_to_vacancy(vacancyId, phone)

    # Единый вывод в консоль и лог
    messages = [
        f"VacancyId: {vacancyId}, Phone: {phone}, Status: {status}, Response: {response}",
        f"Сделано {cnt} из {total}."
    ]

    for msg in messages:
        print(msg)
        if enable_log:
            log_handle.write(msg + '\n')

# Закрываем файл, если использовали
if enable_log:
    log_handle.close()
'''
