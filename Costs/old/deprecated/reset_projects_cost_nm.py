import requests
import json


with open('D:/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# удаление ставок с проекта по 220656035|13786571|85926978  projectId, cityGroupId, categoryId

cnt = 0
with open('D:/python/VentraGO/PROD/costs/reset_project_cost.txt', 'r') as c:
    file_line = sum(1 for line in c)

def reset_project_cost(projectId, categoryId, cityGroupId):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {
        'categoryId': categoryId,
        'cityGroupId': cityGroupId,
    }
    endpoint_url = f'https://{host}/admin/costs/v1/project-costs/{projectId}/rates'
    r = requests.delete(endpoint_url, headers=headers, params=params)
    return r.json()


with open('D:/python/VentraGO/PROD/costs/reset_project_cost.txt', 'r') as c:
    for line in c:
        cnt += 1
        projectId, cityGroupId, categoryId = line.strip().split("|")
        print(reset_project_cost(projectId, cityGroupId, categoryId))
        print(f'Сделано {cnt} из {file_line}.')


