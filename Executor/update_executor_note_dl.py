import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# executor UUID

def add_note(executor_Uid):
    headers = {'Authorization': auth}

    json_data = {"description": "расторжение договора гпх"}

    endpoint_url = f"https://{host}/admin/{executor_Uid}/note"
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


executor_Uid = []
with open('D:/WORK/python/list_userId.txt') as f:
    for line in f.readlines():
        executor_Uid.append(line.strip())

total = len(executor_Uid)
cnt = 0

for uid in executor_Uid:
    status, response = add_note(uid)
    print(f"ExecutorUid: {uid}, Status: {status}")
    cnt += 1
    print(f'Сделано {cnt} из {total}.')