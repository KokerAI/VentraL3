import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# true   false

def change_project_med(project_id):
    headers = {'Authorization': auth.strip()}
    params = {
        'update-vacancies': 'true',
        'update-activities': 'false',
        'medbook': 'false',
    }
    endpoint_url = f'https://{host}/admin/support/change-project-med/{project_id}'
    r = requests.post(endpoint_url, headers=headers, params=params)
    return r.status_code, r.text


project_id = []
with open('D:/WORK/python/list_projectId.txt', 'r') as file:
    for line in file:
        project_id.append(line.strip())

for p in project_id:
    print(change_project_med(p))
