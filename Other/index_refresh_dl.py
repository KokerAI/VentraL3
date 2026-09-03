import requests


with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# Обновление индексов из файла

def refresh_index (index_id):
    headers = {'Authorization': auth.strip(), 'Content-Type': 'application/json'}
    json_data = {
        'type': 'Vacancy', # Executor Project Vacancy
        'ids': [index_id],
    }

    endpoint_url = f'https://{host}/admin/support/refresh-indexes'
    r = requests.post(endpoint_url, headers=headers,json=json_data)
    return r.status_code, r.text


index_ids = []
with open('D:/WORK/python/index.txt', 'r', encoding='utf-8') as c:
    for line in c:
        id_str = line.strip()
        if id_str:
            index_ids.append(int(id_str))

total = len(index_ids)
cnt = 0

for id in index_ids:
    status, response = refresh_index(id)
    print(f"EntityId: {id}, Status: {status}")
    cnt += 1
    print(f'Сделано {cnt} из {total}.')
