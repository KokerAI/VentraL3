import requests
import json

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'

# обновить ставку по вакансиям в формате: 190305907|123.45|16      vacancyId|rate|marginality


cnt = 0
with open('D:/WORK/python/update_vacancy_cost.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


def update_vacancy_cost(vacancyId, rate, marginality):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'rate': rate,
        'marginality': marginality,
        'flowType': 'Base',  # Final  Base
        'vacancyId': vacancyId,
    }

    endpoint_url = f'https://{host}/admin/costs/vacancy-costs/update'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/update_vacancy_cost.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        vacancyId, rate, marginality = line.strip().split("|")
        print(vacancyId, update_vacancy_cost(vacancyId, rate, marginality))
        print(f'Сделано {cnt} из {file_line}.')
