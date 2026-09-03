import requests
import json

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
    host = 'api.dap.ventra.ru/api'

# удаление ставок с заданий по  220656035|13786571|85926978   vacancy_id|cityGroupId|categoryId

cnt = 0
with open('D:/WORK/python/reset_vacancy_cost.txt', 'r') as c:
    file_line = sum(1 for line in c)


def reset_project_cost(vacancy_id, cityGroupId, categoryId):
    headers = {'Authorization': auth.strip()}
    params = {
        'categoryId': categoryId,
        'cityGroupId': cityGroupId}

    endpoint_urt = f'https://{host}/admin/costs/v1/vacancy-costs/{vacancy_id}/rates'
    r = requests.delete(endpoint_urt, headers=headers, params=params)
    return r.status_code, r.json()


with open('D:/WORK/python/reset_vacancy_cost.txt', 'r') as c:
    for line in c:
        cnt += 1
        vacancy_id, cityGroupId, categoryId = line.strip().split("|")
        print(vacancy_id, reset_project_cost(vacancy_id, cityGroupId, categoryId))
        print(f'Сделано {cnt} из {file_line}.')
