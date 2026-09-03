import os
import requests
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# === НАСТРОЙКИ ===
max_workers = 30  # Настройка многопоточности
enable_log = True  # True False
host = 'https://api.dap.ventra.ru/api/v1/brands/save/'
# host = 'api.stage.dap.ventra.ru/api/v1/brands/save/'
auth_file = 'D:/WORK/python/auth.txt'
brand_ids_file = 'D:/WORK/python/list_brandId.txt'
executor_ids_file = 'D:/WORK/python/list_userId.txt'
script_name = os.path.basename(__file__)

# === НАСТРОЙКИ ТОКЕНА ===
# Токен живет 24 часа, обновляем каждые 23 часа для надежности
TOKEN_REFRESH_INTERVAL = 23 * 3600  # 23 часа в секундах
last_token_refresh = 0
auth_token = None
token_lock = Lock()

# Лог файл в папке скрипта:
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'brand_executor_processing.log')


# === ФУНКЦИИ ===
def load_auth(auth_file):
    with open(auth_file) as f:
        return f.readline().strip()


def get_token():
    global last_token_refresh, auth_token
    with token_lock:
        current_time = time.time()
        if auth_token is None or (current_time - last_token_refresh) > TOKEN_REFRESH_INTERVAL:
            auth_token = load_auth(auth_file)
            last_token_refresh = current_time
            print(f"🔄 Токен обновлен. Следующее обновление через {TOKEN_REFRESH_INTERVAL // 3600} часов")
    return auth_token


def process_task(executor_id, brand_id):
    auth = get_token()
    try:
        json_data = {
            "brandId": int(brand_id),
            "executorId": int(executor_id),
            "brandListStatus": "Processed",
            "startTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        headers = {
            'accept': 'application/hal+json',
            'Content-Type': 'application/json',
            'Authorization': auth
        }

        response = requests.post(host, json=json_data, headers=headers, timeout=10)

        is_success = 200 <= response.status_code < 300
        status = "УСПЕХ" if is_success else "ОШИБКА"
        result = {
            "executor_id": executor_id,
            "brand_id": brand_id,
            "status": status,
            "status_code": response.status_code,
            "response": response.text if is_success else f"Error: {response.text}"
        }
        return result

    except Exception as e:
        return {
            "executor_id": executor_id,
            "brand_id": brand_id,
            "status": "ОШИБКА",
            "status_code": "EXCEPTION",
            "response": f"Ошибка: {str(e)}"
        }


def log_messages(messages, log_file):
    if enable_log:
        with open(log_file, 'a', encoding='utf-8') as log:
            for msg in messages:
                log.write(msg + '\n')


# === ОСНОВНОЙ КОД ===
print(f"✅ Авторизация загружена. Начало обработки...")

# Чтение списков
brand_ids = [line.strip() for line in open(brand_ids_file) if line.strip().isdigit()]
executor_ids = [line.strip() for line in open(executor_ids_file) if line.strip().isdigit()]

if not brand_ids or not executor_ids:
    print("❌ Ошибка: не найдены корректные ID в файлах")
    exit(1)

total = len(executor_ids) * len(brand_ids)
print(f"🔍 Найдено: {len(executor_ids)} исполнителей и {len(brand_ids)} брендов. Всего комбинаций: {total}")

# Инициализация лога
if enable_log:
    with open(log_file, 'w', encoding='utf-8') as log:
        log.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        log.write(
            f"Найдено: {len(executor_ids)} исполнителей и {len(brand_ids)} брендов. Всего комбинаций: {total}\n\n")

# Первая загрузка токена
auth_token = load_auth(auth_file)
last_token_refresh = time.time()
print(f"🔐 Токен загружен. Интервал обновления: {TOKEN_REFRESH_INTERVAL // 3600} часов")

# Формирование списка задач
tasks = [(executor_id, brand_id) for executor_id in executor_ids for brand_id in brand_ids]

# Параллельная обработка
print(f"🚀 Запуск обработки с {max_workers} потоками...")
start_time = time.time()
completed = 0

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_task, executor_id, brand_id) for executor_id, brand_id in tasks]

    for future in as_completed(futures):
        completed += 1
        result = future.result()

        # Формируем и выводим результат
        print(
            f"[{result['status']}] Executor: {result['executor_id']}, Brand: {result['brand_id']}, Status: {result['status_code']}")
        print(result['response'])
        print(f"Сделано {completed} из {total}.")

        # Логирование
        if enable_log:
            log_messages([
                f"[{result['status']}] Executor: {result['executor_id']}, Brand: {result['brand_id']}, Status: {result['status_code']}",
                result['response'],
                f"Сделано {completed} из {total}.",
                ""
            ], log_file)

        # Показываем прогресс каждые 100 задач
        if completed % 100 == 0:
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            remaining = (total - completed) / speed if speed > 0 else 0
            print(f"⏳ Прогресс: {completed}/{total} ({completed / total:.1%}), "
                  f"скорость: {speed:.1f} запросов/сек, "
                  f"осталось: {remaining / 60:.1f} мин\n")

# Завершение
elapsed = time.time() - start_time
print(f"✅ Обработка завершена! Всего обработано: {total} комбинаций за {elapsed:.2f} секунд")
print(f"📊 Средняя скорость: {total / elapsed:.1f} запросов/сек")

if enable_log:
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"\n✅ Обработка завершена! Всего обработано: {total} комбинаций за {elapsed:.2f} секунд\n")
        log.write(f"📊 Средняя скорость: {total / elapsed:.1f} запросов/сек\n")
