import sys
import os
import requests
import psycopg2
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent));
from db_config import get_db_config

# === НАСТРОЙКИ ===
paid_by_client = False  # True False
reason = 'Overbooking'  # Overbooking Other Fraud
min_val = 720  # Фикс кол-во минут
comment = 'Вопрос #267473123'  # Номер заявки
host = 'api.dap.ventra.ru'
# host = 'api.stage.ventra.ru'
auth_file = 'D:/WORK/python/auth.txt'
activities_file = 'D:/WORK/python/list_activities.txt'
minutes_file = 'D:/WORK/python/list_minutes.txt'
comments_file = 'D:/WORK/python/list_comments.txt'
max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
db_config = get_db_config()  # Динамическая загрузка из .ENV


# === ФУНКЦИИ ===
def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def check_db_connection():
    """Проверяет подключение к БД и прерывает выполнение при ошибке"""
    try:
        with psycopg2.connect(connect_timeout=10, **db_config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        error_text = str(e)
        error_msg = error_text.split("FATAL:")[1].strip() if "FATAL:" in error_text else error_text
        sys.exit(f"\n❌ DB error: {error_msg}\n")


def get_vacancy_executor(activity_id):
    """Получает vacancy_id и executor_id по activity_id"""
    with psycopg2.connect(**db_config) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vacancy_id, executor_id FROM executor_work_activity WHERE id = %s", (activity_id,))
            result = cur.fetchone()
            if result and None not in result:
                return int(result[0]), int(result[1])
    return None, None


def suspend_activity(vacancy_id, executor_id, minutes, final_comment):
    """Компенсация активностей"""
    try:
        headers = {
            'Authorization': load_auth().strip(),
            'content-type': 'application/json',
            'accept': '*/*'
        }
        json_data = {
            'executorId': executor_id,
            'minutes': int(minutes),
            'reason': reason,
            'comment': final_comment,
            'paidByCompany': paid_by_client
        }
        url = f'https://{host}/api/admin/support/assign/vacancy/{vacancy_id}/suspend'
        return requests.put(url, headers=headers, json=json_data, timeout=30).status_code
    except Exception as e:
        return f'Error: {str(e)}'


def process_activity(activity_id, minutes_val, current_comment):
    """Обрабатывает одну активность с комментарием"""
    vacancy_id, executor_id = get_vacancy_executor(activity_id)
    if not vacancy_id or not executor_id:
        return activity_id, minutes_val, 404, "Data not found in DB"
    return activity_id, minutes_val, suspend_activity(vacancy_id, executor_id, minutes_val, current_comment), ""


def statistics():
    """Итоговая статистика"""
    duration = (datetime.now() - start).total_seconds()
    print(f"\n✅ Completed {success}/{total} activities in {duration:.2f} seconds")
    print(f"📈 Speed: {total / duration:.1f} req/sec" if duration > 0 else "")


# === ОСНОВНОЙ КОД ===
check_db_connection()
start = datetime.now()

# Загрузка доп. комментариев (если файл существует)
custom_comments = []
if os.path.exists(comments_file):
    with open(comments_file, 'r', encoding='utf-8') as file:
        custom_comments = [line.rstrip('\r\n').strip() for line in file]

'''
# === ФИКСИРОВАННОЕ КОЛИЧЕСТВО МИНУТ (min_val) ===
with open(activities_file) as f:
    activities_id = [line.strip() for line in f if line.strip()]

total, success = len(activities_id), 0

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {}
    for i, activity_id in enumerate(activities_id):
        current_comment = comment
        if i < len(custom_comments) and custom_comments[i]:
            current_comment = f"{comment} {custom_comments[i]}" if comment.strip() else custom_comments[i]

        future = executor.submit(process_activity, activity_id, min_val, current_comment)
        futures[future] = (activity_id, min_val, current_comment)

    for i, future in enumerate(as_completed(futures), 1):
        activity_id, mins, current_comment = futures[future]
        _, _, status, response = future.result()

        icon = "✅" if (isinstance(status, int) and 200 <= status < 300) else "❌"
        print(f"{icon} Activity: {activity_id}, Minutes: {mins}, Status: {status}, Comment: '{current_comment}'")
        print(f"Сделано {i} из {total}.")

        if isinstance(status, int) and 200 <= status < 300:
            success += 1

statistics()

'''

# === РАЗНОЕ КОЛИЧЕСТВО МИНУТ (list_minutes) ===
with open(activities_file) as f: activities_id = [line.strip() for line in f if line.strip()]
with open(minutes_file) as f: minutes = [line.strip() for line in f if line.strip()]

if len(activities_id) != len(minutes):
    print(f"⚠️ Count mismatch: activities({len(activities_id)}) vs minutes({len(minutes)})")
    sys.exit(1)

total, success = len(activities_id), 0

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {}
    for i, (aid, mins) in enumerate(zip(activities_id, minutes)):
        current_comment = comment
        if i < len(custom_comments) and custom_comments[i]:
            current_comment = f"{comment} {custom_comments[i]}" if comment.strip() else custom_comments[i]

        future = executor.submit(process_activity, aid, mins, current_comment)
        futures[future] = (aid, mins, current_comment)

    for i, future in enumerate(as_completed(futures), 1):
        activity_id, mins, current_comment = futures[future]
        _, _, status, response = future.result()

        icon = "✅" if (isinstance(status, int) and 200 <= status < 300) else "❌"
        print(f"{icon} Activity: {activity_id}, Minutes: {mins}, Status: {status}, Comment: '{current_comment}'")
        print(f"Сделано {i} из {total}.")

        if isinstance(status, int) and 200 <= status < 300:
            success += 1

statistics()
