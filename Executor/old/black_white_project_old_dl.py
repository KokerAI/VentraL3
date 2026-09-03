import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# Добавление испа в чс/прескрин проекта в формате:   projectId|executorUid   248836379|5e275ba8-e504-479a-b29a-39deb590be64

def black_prescreen_executor(projectId, executorUid):
    headers = {'Authorization': auth.strip(), 'accept': '*/*', 'Content-Type': 'application/json'}
    params = {'listType': 'WHITE_PRESCREENING'} # WHITE_PRESCREENING BLACK
    data = executorUid

    endpoint_url = f'https://{host}/admin/projects/executor/update/{projectId}'
    r = requests.post(endpoint_url, params=params, headers=headers,data=data)
    return r.status_code, r.text


cnt = 0
with open('D:/WORK/python/list_userId.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)

with open('D:/WORK/python/list_userId.txt', 'r', encoding='utf-8') as c:
    for line in c:
        projectId, executorUid = line.strip().split("|")
        status, response = black_prescreen_executor(projectId, executorUid)
        print(f"Project: {projectId}, Executor: {executorUid}, Status: {status}")
        cnt += 1
        print(f'Сделано {cnt} из {file_line}.')