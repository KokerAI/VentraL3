import os
import threading
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# СБРОС СТАВОК C АКТИВНОСТЕЙ: 220656035   vacancyId

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))
lock = threading.Lock()

with open('D:/WORK/python/reset_activity_cost.txt', 'r') as c:
    lines = [line.strip() for line in c if line.strip()]
total = len(lines)


def reset_activity_cost(vacancy_id):
    headers = {'Authorization': auth, 'accept': '*/*'}
    params = {'vacancyIds': vacancy_id}
    endpoint_url = f'https://{host}/admin/costs/v1/activity-costs'
    r = requests.delete(endpoint_url, headers=headers, params=params)
    return r.status_code, r.text


def process_line(line):
    activity_id = line
    status_code, response = reset_activity_cost(activity_id)
    return activity_id, status_code, response


with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_line, line) for line in lines]
    for i, future in enumerate(as_completed(futures), 1):
        activity_id, status_code, response = future.result()
        with lock:
            print(f'Activity: {activity_id}, Status: {status_code}, {response}')
            print(f'Сделано {i} из {total}.')
