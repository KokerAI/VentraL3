import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
    host = 'api.dap.ventra.ru/api'

is_archive = True  # True False

def project_archive(project_id):
    headers = {'Authorization': auth.strip()}
    archive_param = "true" if is_archive else "false"
    endpoint_url = f'https://{host}/admin/projects/archive/{project_id}?archive={archive_param}'
    r = requests.patch(endpoint_url, headers=headers)
    return r.status_code, r.text

project_ids = []
with open('D:/WORK/python/list_projectId.txt', 'r') as file:
    for line in file:
        project_ids.append(line.strip())

total = len(project_ids)
cnt = 0

for project_id in project_ids:
    status, response = project_archive(project_id)
    print(f"Project ID: {project_id}, Status: {status}, Response: {response}")
    cnt += 1
    print(f"Сделано {cnt} из {total}.")