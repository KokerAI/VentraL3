import os
import sys
import requests
import psycopg2
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent));
from db_config import get_db_config

# ПОДТВЕРЖДАЕТ НУЖНОЕ КОЛИЧЕСТВО ЧАСОВ ИЗ ФАЙЛОВ

# ПОМЕНЯТЬ КОММЕНТ!!!
comment = 'Вопрос #000000000'
min_val = 720
activities_file = 'D:/WORK/python/list_activities.txt'
minutes_file = 'D:/WORK/python/list_minutes.txt'
comments_file = 'D:/WORK/python/list_comments.txt'
host = 'api.dap.ventra.ru/api'

db_config = get_db_config()   # Динамическая загрузка из .ENV

# db_config = {
#     'dbname': 'your_db',
#     'user': 'your_user',
#     'password': 'your_password',
#     'host': 'your_host',
#     'port': '5432'
# }

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()


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


'''
# ПОДТВЕРЖДАЕТ ОДИНАКОВОЕ (min_val) КОЛИЧЕСТВО МИНУТ ДЛЯ ВСЕХ АКТИВНОСТЕЙ
def update_activities_hours(activity_id, minutes_val, comment):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {'minutes': str(minutes_val), }
    json_data = {'comment': comment, }

    endpoint_url = f'https://{host}/admin/activities/comments/{activity_id}'
    r = requests.put(endpoint_url, headers=headers, params=params, json=json_data)
    return r.status_code, r.text

activities_id = []
if not os.path.exists(activities_file):
    sys.exit(f"❌ Файл с активностями не найден: {activities_file}")
with open(activities_file, 'r') as file:
    for line in file:
        activities_id.append(line.strip())

custom_comments = []
if os.path.exists(comments_file):
    with open(comments_file, 'r', encoding='utf-8') as file:
        custom_comments = [line.rstrip('\r\n').strip() for line in file]

total = len(activities_id)
cnt = 0

for i in range(total):
    current_comment = comment
    if i < len(custom_comments) and custom_comments[i]:
        if comment.strip():
            current_comment = f"{comment} {custom_comments[i]}"
        else:
            current_comment = custom_comments[i]

    status, response = update_activities_hours(activities_id[i], min_val, current_comment)
    print(f"{activities_id[i]}, {min_val}, Status: {status}, Response: {response}")
    if status == 200:
        if fix_activity_timework(activities_id[i]):
            print(f"✅ Timework для активности {activities_id[i]} обновлен")
    
    cnt += 1
    print(f"Сделано {cnt} из {total}.")
'''



# ПОДТВЕРЖДАЕТ РАЗНОЕ КОЛИЧЕСТВО МИНУТ ДЛЯ АКТИВНОСТЕЙ (ИЗ ФАЙЛА)
def update_activities_hours(activity_id, minutes_val, comment):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {'minutes': minutes_val, }
    json_data = {'comment': comment, }

    endpoint_url = f'https://{host}/admin/activities/comments/{activity_id}'
    r = requests.put(endpoint_url, headers=headers, params=params, json=json_data)
    return r.status_code, r.text


activities_id = []
if not os.path.exists(activities_file):
    sys.exit(f"❌ Файл с активностями не найден: {activities_file}")
with open(activities_file, 'r') as file:
    for line in file:
        activities_id.append(line.strip())

minutes = []
if not os.path.exists(minutes_file):
    sys.exit(f"❌ Файл с минутами не найден: {minutes_file}")
with open(minutes_file, 'r') as file:
    for mins in file:
        minutes.append(mins.strip())

custom_comments = []
if os.path.exists(comments_file):
    with open(comments_file, 'r', encoding='utf-8') as file:
        custom_comments = [line.rstrip('\r\n').strip() for line in file]

if len(activities_id) != len(minutes):
    print("Количество activityId и минут не совпадает!")
    exit()

total = len(activities_id)
cnt = 0

for i in range(total):
    current_comment = comment
    if i < len(custom_comments) and custom_comments[i]:
        if comment.strip():
            current_comment = f"{comment} {custom_comments[i]}"
        else:
            current_comment = custom_comments[i]

    status, response = update_activities_hours(activities_id[i], minutes[i], current_comment)
    print(f"{activities_id[i]}, {minutes[i]}, Status: {status}, Response: {response}")
    if status == 200:
        if fix_activity_timework(activities_id[i]):
            print(f"✅ Timework для активности {activities_id[i]} обновлен")

    cnt += 1
    print(f"Сделано {cnt} из {total}.")
