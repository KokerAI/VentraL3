import requests


with open('D:/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# обновить ставку по проектам с субсидиями:         190305907|123.45      projectId, executorRateWithSubsidy            subsidyAmount - опционально


cnt = 0
with open('D:/python/VentraGO/PROD/costs/update_project_cost_999.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


def update_project_cost(projectId, executorRateWithSubsidy):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'projectId': projectId,
        'executorRateWithSubsidy': executorRateWithSubsidy,
    }

    endpoint_url = f'https://{host}/admin/costs/project-costs/save-subsidy'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code


with open('D:/python/VentraGO/PROD/costs/update_project_cost_999.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        projectId, executorRateWithSubsidy = line.strip().split("|")
        print(update_project_cost(projectId, executorRateWithSubsidy))
        print(f'Сделано {cnt} из {file_line}.')

