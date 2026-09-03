import requests
import json

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# обновить ставку по проектам в формате: 190305907|123.45|16   projectId|rate|marginality
# ПРОВЕРЯТЬ flowType БАЗОВАЯ ИЛИ КЛИЕНТСКАЯ !!!

cnt = 0
with open('D:/WORK/python/update_project_cost_999.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


def update_project_cost(projectId, rate, marginality):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'rate': rate,
        'marginality': marginality,
        'flowType': 'Base',  # Final  Base
        'projectId': projectId,
    }

    endpoint_url = f'https://{host}/admin/costs/project-costs/update'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/update_project_cost_999.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        projectId, rate, marginality = line.strip().split("|")
        print(projectId, update_project_cost(projectId, rate, marginality))
        print(f'Сделано {cnt} из {file_line}.')
