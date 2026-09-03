import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
# host = 'api.stage.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# Для разлогина юзера со всех устройств в формате: executorUid   95fc7624-3d5d-434c-9dfa-6af4bc4ca464

def executor_force_logout(executorUid):
    headers = {'Authorization': auth}
    params = {'uuid': executorUid}
    endpoint_url = f'https://{host}/v1/force-logout'
    r = requests.post(endpoint_url, headers=headers, params=params)
    return r.status_code, r.text


user_ids = []
with open('D:/WORK/python/list_userId.txt', 'r', encoding='utf-8') as file:
    for line in file:
        user_id = line.strip()
        if user_id:
            user_ids.append(user_id)

total = len(user_ids)
cnt = 0

for uid in user_ids:
    status, response = executor_force_logout(uid)
    print(f"ExecutorUid: {uid}, Status: {status}")
    cnt += 1
    print(f'Сделано {cnt} из {total}.')