import os
import threading
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# СБРОС СТАВОК С ВАКАНСИЙ: 220656035|13786571|85926978   vacancyId|cityGroupId|categoryId

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)
lock = threading.Lock()


with open('D:/WORK/python/reset_vacancy_cost.txt', 'r') as c:
    lines = [line.strip() for line in c if line.strip()]
total = len(lines)


def reset_vacancy_cost(vacancyId, cityGroupId, categoryId):
    headers = {'Authorization': auth}
    params = {
        'categoryId': categoryId,
        'cityGroupId': cityGroupId,
    }
    endpoint_url = f'https://{host}/admin/costs/v2/vacancy-costs/{vacancyId}/rates'
    r = requests.delete(endpoint_url, headers=headers, params=params)
    return r.status_code, r.text


def process_line(line):
    vacancyId, cityGroupId, categoryId = line.split("|")
    status_code, response = reset_vacancy_cost(vacancyId, cityGroupId, categoryId)
    return vacancyId, status_code, response


with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_line, line) for line in lines]
    for i, future in enumerate(as_completed(futures), 1):
        vacancyId, status_code, response = future.result()
        with lock:
            print(f'Vacancy: {vacancyId}, Status: {status_code}, {response}')
            print(f'Сделано {i} из {total}.')


