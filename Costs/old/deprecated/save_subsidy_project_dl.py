import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

cnt = 0
with open('D:/WORK/python/save_subsidy_project.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


# Обновить субсидии по проекту:    projectId, executorRateWithSubsidy
#

def save_subsidy_project(projectId, executorRateWithSubsidy):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'executorRateWithSubsidy': executorRateWithSubsidy,
        'projectId': projectId,
    }

    endpoint_url = f'https://{host}/admin/costs/project-costs/save-subsidy'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/save_subsidy_project.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        projectId, executorRateWithSubsidy = line.strip().split("|")
        print(projectId, save_subsidy_project(projectId, executorRateWithSubsidy))
        print(f'Сделано {cnt} из {file_line}.')


