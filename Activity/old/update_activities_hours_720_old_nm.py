import json
import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
    host = 'api.dap.ventra.ru/api'

comment = 'Вопрос #000000000'
min_val = 720

'''
# ПОМЕНЯТЬ КОММЕНТ!!!
# ПОДТВЕРЖДАЕТ ОДИНАКОВОЕ (min_val) КОЛИЧЕСТВО МИНУТ ДЛЯ ВСЕХ АКТИВНОСТЕЙ

def update_activities_hours(activity_id, minutes):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {'minutes': str(minutes), }
    json_data = {'comment': comment, }
    
    endpoint_url = f'https://{host}/admin/activities/comments/{activity_id}'
    r = requests.put(endpoint_url, headers=headers, params=params, json=json_data)
    return r.status_code, r.text


activities_id = []
with open('D:/WORK/python/list_activities.txt', 'r') as file:
    for line in file:
        activities_id.append(line.strip())

total = len(activities_id)
cnt = 0

for i in range(total):
    status, response = update_activities_hours(activities_id[i], min_val)
    print(f"{activities_id[i]}, {min_val}, Status: {status}, Response: {response}")
    cnt += 1
    print(f"Сделано {cnt} из {total}.")

'''


# ПОМЕНЯТЬ КОММЕНТ!!!
# ПОДТВЕРЖДАЕТ РАЗНОЕ КОЛИЧЕСТВО МИНУТ ДЛЯ АКТИВНОСТЕЙ (ИЗ ФАЙЛА)

def update_activities_hours(activities_id, minutes):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {'minutes': minutes, }
    json_data = {'comment': comment, }

    endpoint_url = f'https://{host}/admin/activities/comments/{activities_id}'
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

if len(activities_id) != len(minutes):
    print("Количество activityId и минут не совпадает!")
    exit(1)

total = len(activities_id)
cnt = 0

for i in range(total):
    status, response = update_activities_hours(activities_id[i], minutes[i])
    print(f"{activities_id[i]}, {minutes[i]}, Status: {status}, Response: {response}")
    cnt += 1
    print(f"Сделано {cnt} из {total}.")
