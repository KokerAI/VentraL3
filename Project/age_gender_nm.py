import json
import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# 0 - "MALE"/   1 - "FEMALE"/   2 - "NONE"
# Если "gender" заполнен - по умолчанию передается "NONE" (2)
# обновление возраста на несколько проектов из файла list_projectId.txt :

cnt = 0
with open('D:/WORK/python/list_projectId.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


def update_age_projectId(project_id):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        "person": {
            # "gender": "MALE",
            "minAge": 18,
            "maxAge": 75
        },
    }
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r, r.text


# project_id = []
# with open('D:/WORK/python/list_projectId.txt', 'r') as file:
#     for line in file:
#         project_id.append(line.strip())

# for p in project_id:
#     print(update_age_projectId(p))


with open('D:/WORK/python/list_projectId.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        project_id = line.strip()
        print(update_age_projectId(project_id))
        print(f'Сделано {cnt} из {file_line}.')

'''

# 0 - "MALE"/   1 - "FEMALE"/   2 - "NONE"

cnt = 0
with open('D:/WORK/python/list_projectId.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


#   240104048|NONE|18|70

def update_age_projectId(project_id,gender,minAge,maxAge):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        "person": {
           "gender": gender,
            "minAge": minAge,
            "maxAge": maxAge
    },
    }
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r, r.text

with open('D:/WORK/python/list_projectId.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        project_id,gender,minAge,maxAge = line.strip().split("|")
        print(update_age_projectId(project_id,gender,minAge,maxAge))
        print(f'Сделано {cnt} из {file_line}.')



'''

'''
 СТАРОЕ НЕ АКТУАЛЬНО
# если ругается на сити груп, вместо CURL после изменения в БД:

def update_age_projectId_DB(ids):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {
        'ids': ids,
        'batchSize': '100',
    }
    endpoint_url = f'https://{host}/admin/support/fill-matching-service-5-projects'
    r = requests.get(endpoint_url, headers=headers, params=params)
    return r, r.text
# print(update_age_projectId_DB())

ids = []
with open('D:/WORK/python/list_projectId.txt', 'r') as file:
    for line in file:
        ids.append(line.strip())

for p in ids:
    print(update_age_projectId_DB(p))



'''
