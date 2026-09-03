import json
import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'

cnt = 0
with open('D:/WORK/python/address_geo.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


#   000000000|Электролитный проезд, 16А, Москва, 115230|55.673311|37.612108
#   000000000|000000000000000000000|00000000|000000000

def update_address_geo(projects_id, address, latitude, longitude):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'address': address,
        'latitude': latitude,
        'longitude': longitude,
    }

    endpoint_url = f'https://{host}/admin/projects/{projects_id}'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/address_geo.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        projects_id, address, latitude, longitude = line.strip().split("|")
        print(update_address_geo(projects_id, address, latitude, longitude))
        print(f'Сделано {cnt} из {file_line}.')
