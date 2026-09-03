import json
import requests

#     Обновление ГЕО по проекту

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


cnt = 0
with open('D:/WORK/python/address_geo.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


# 318582384|55.754694|37.621417
# 000000000|00.000000|00.000000

def update_geo_projectId(projects_id, latitude, longitude):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'latitude': latitude,
        'longitude': longitude,
    }
    endpoint_url = f'https://{host}/admin/projects/{projects_id}'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text
# print(update_geo_projectId(	59.962740, 30.294149))


with open('D:/WORK/python/address_geo.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        projects_id, latitude, longitude = line.strip().split("|")
        print(update_geo_projectId(projects_id, latitude, longitude))
        print(f'Сделано {cnt} из {file_line}.')