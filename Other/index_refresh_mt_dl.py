import os
import requests
from concurrent.futures import ThreadPoolExecutor

# Обновление индексов из файла

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.ventra.ru/api'
host = 'api.dap.ventra.ru/api'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)


def refresh_index(index_id):
    headers = {'Authorization': auth.strip(), 'Content-Type': 'application/json'}
    json_data = {
        'type': 'Executor', # Executor Project Vacancy
        'ids': [index_id],
    }
    endpoint_url = f'https://{host}/admin/support/refresh-indexes'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


index_ids = []
with open('D:/WORK/python/index.txt', 'r', encoding='utf-8') as c:
    for line in c:
        id_str = line.strip()
        if id_str:
            index_ids.append(int(id_str))

total = len(index_ids)


def worker(idx):
    return idx, *refresh_index(idx)


with ThreadPoolExecutor(max_workers=max_workers) as executor:
    cnt = 0
    for idx, status, _ in executor.map(worker, index_ids):
        print(f"EntityId: {idx}, Status: {status}")
        cnt += 1
        print(f'Сделано {cnt} из {total}.')
