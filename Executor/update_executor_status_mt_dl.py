import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'
lock = threading.Lock()
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)


def update_status(executor_Uid):
    headers = {
        'Authorization': auth.strip(),
        'accept': '*/*',
        'Content-Type': 'application/json'
    }

    json_data = {
        'status': 'PENDING', #ACTIVE, PENDING, BLOCKED, DELETED
        # 'type': 'PERMANENT', #PERMANENT TEMPORARY
        # 'hours': 0,
        # 'reason': 'расторжение договора гпх',
    }

    endpoint_url = f'https://{host}/admin/v2/executor/{executor_Uid}/status'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return executor_Uid, r.status_code, r.text


executor_Uid = []
with open('D:/WORK/python/list_userId.txt', 'r') as file:
    for line in file:
        executor_Uid.append(line.strip())

total = len(executor_Uid)
max_workers = min(32, (os.cpu_count() or 1) * 5)

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(update_status, uid): uid for uid in executor_Uid}

    for i, future in enumerate(as_completed(futures), 1):
        try:
            uid, status, response = future.result()
            with lock:
                print(f'✅ {uid} | Status: {status} | Response: {response[:50]}...')
        except Exception as e:
            uid = futures[future]
            with lock:
                print(f'❌ Error {uid}: {str(e)}')
        finally:
            with lock:
                print(f'Сделано {i} из {total}')