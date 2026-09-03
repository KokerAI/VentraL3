import requests
import json

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# обновить ставку по активностям в формате: 190305907|123.45|16   activityId|rate|marginality
# ПРОВЕРЯТЬ flowType БАЗОВАЯ ИЛИ КЛИЕНТСКАЯ !!!

cnt = 0
with open('D:/WORK/python/save_activity_cost.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


def update_activity_cost(activityId, rate, marginality):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'rate': rate,
        'marginality': marginality,
        'flowType': 'Base',  # Final  Base
        'activityId': activityId,
    }

    endpoint_url = f'https://{host}/admin/costs/activity-costs/save'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/save_activity_cost.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        activityId, rate, marginality = line.strip().split("|")
        print(update_activity_cost(activityId, rate, marginality))
        print(f'Сделано {cnt} из {file_line}.')
