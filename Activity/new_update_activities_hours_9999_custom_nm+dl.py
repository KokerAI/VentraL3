import sys
import requests
import psycopg2
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent));from db_config import get_db_config

# КОРРЕКТИРУЕТ НУЖНОЕ КОЛИЧЕСТВО ЧАСОВ ИЗ ФАЙЛОВ В СТАТУСАХ:
# FUNDS_AVAILABLE
# TIME_APPROVED
# WORKER_PAID_FULLY (только увеличение количетсва минут)

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
host = 'sdr-api.dap.ventra.ru/payment-transactions'
db_config = get_db_config()   # Динамическая загрузка из .ENV


# Конфигурация БД (ЗАПОЛНИТЬ АКТУАЛЬНЫМИ ДАННЫМИ)
# db_config = {
#     'dbname': 'your_db',
#     'user': 'your_user',
#     'password': 'your_password',
#     'host': 'your_host',
#     'port': '5432'
# }


def fix_activity_timework(activity_id):
    """Копирует start_time_work и end_time_work из вакансии в активность при NULL"""
    try:
        with psycopg2.connect(**db_config) as conn, conn.cursor() as cursor:
            cursor.execute("""
                UPDATE executor_work_activity ewa
                SET start_time_work = v.start_time, end_time_work = v.end_time
                FROM vacancies v
                WHERE ewa.vacancy_id = v.id AND ewa.id = %s 
                AND (ewa.start_time_work IS NULL OR ewa.end_time_work IS NULL)
                RETURNING 1
            """, (activity_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        print(f"⚠️ Ошибка обновления timework для {activity_id}: {str(e)}")
    return False


def update_activities_hours(activities_id, minutes):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {
        'activityId': activities_id,
        'minutes': minutes,
    }
    endpoint_url = f'https://{host}/ops/update-confirmed-hours'
    r = requests.patch(endpoint_url, headers=headers, params=params)
    return r, r.text


activities_id = []
with open('D:/WORK/python/list_activities.txt', 'r') as file:
    for line in file:
        activities_id.append(line.strip())

minutes = []
with open('D:/WORK/python/list_minutes.txt', 'r') as file:
    for mins in file:
        minutes.append(mins.strip())

if len(activities_id) != len(minutes):
    print("Количество activityId и минут не совпадает!")
    exit(1)

total = len(activities_id)
cnt = 0

for i in range(total):
    r, response = update_activities_hours(activities_id[i], minutes[i])
    print(f"{activities_id[i]}, {minutes[i]}, Status: {r.status_code}, Response: {response}")

    # Вызываем функцию обновления времени только при успешном ответе
    if r.status_code == 200:
        if fix_activity_timework(activities_id[i]):
            print(f"✅ Timework для активности {activities_id[i]} обновлен")

    cnt += 1
    print(f"Сделано {cnt} из {total}.")