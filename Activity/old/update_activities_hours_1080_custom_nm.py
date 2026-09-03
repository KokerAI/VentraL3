import os
import json
import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
    host = 'api.dap.ventra.ru/api'

# ПОМЕНЯТЬ КОММЕНТ!!!
comment = 'Вопрос #000000000'
min_val = 720

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
with open('D:/WORK/python/list_activities.txt', 'r') as file:
    for line in file:
        activities_id.append(line.strip())

custom_comments = []
if os.path.exists('D:/WORK/python/list_comments.txt'):
    with open('D:/WORK/python/list_comments.txt', 'r', encoding='utf-8') as file:
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
with open('D:/WORK/python/list_activities.txt', 'r') as file:
    for line in file:
        activities_id.append(line.strip())

minutes = []
with open('D:/WORK/python/list_minutes.txt', 'r') as file:
    for mins in file:
        minutes.append(mins.strip())

custom_comments = []
if os.path.exists('D:/WORK/python/list_comments.txt'):
    with open('D:/WORK/python/list_comments.txt', 'r', encoding='utf-8') as file:
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
    cnt += 1
    print(f"Сделано {cnt} из {total}.")
