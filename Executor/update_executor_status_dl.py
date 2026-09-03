import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'

# executor UUID

def update_status(executor_Uid):
    headers = {'Authorization': auth.strip(),
               'accept': '*/*',
               'Content-Type': 'application/json'
               }

    json_data = {
        'status': 'ACTIVE', #ACTIVE, PENDING, BLOCKED, DELETED
        # 'type': 'PERMANENT', #PERMANENT TEMPORARY
        'hours': 0,
        'reason': 'расторжение договора гпх',
    }

    endpoint_url = f'https://{host}/admin/v2/executor/{executor_Uid}/status'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


executor_Uid = []
with open('D:/WORK/python/list_userId.txt', 'r') as file:
    for line in file:
        executor_Uid.append(line.strip())

for p in executor_Uid:
    print(update_status(p))
