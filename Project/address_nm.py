import json
import requests

#     Обновление ГЕО по проекту

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# обновление адреса:


cnt = 0
with open('/address_geo.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


def update_address_projectId(projects_id, address):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'address': address,
    }
    endpoint_url = f'https://{host}/admin/projects/{projects_id}'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text
# print(update_address_projectId("ул. Киевская, 189Б, Симферополь, Крым Респ"))

with open('D:/WORK/python/address_geo.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        projects_id, address = line.strip().split("|")
        print(update_address_projectId(projects_id, address))
        print(f'Сделано {cnt} из {file_line}.')










