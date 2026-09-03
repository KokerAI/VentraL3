import json
import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'

'''
# включить овербукинг (СТАНДАРТ)
def update_overbooking(vacancyId):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'vacancyId': vacancyId,
        'overbookingConfigId': 71163782,
        'executorsToDecline': [],
    }
    endpoint_url = f'https://{host}/admin/overbooking/vacancy'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


# print(update_overbooking())


vacancyId = []
with open('D:/WORK/python/list_vacancyId.txt', 'r') as file:
    for line in file:
        vacancyId.append(line.strip())

for p in vacancyId:
    print(update_overbooking(p))

'''


# отключить овербукинг (или включить по количеству)
def update_overbooking(vacancyId):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'vacancyId': vacancyId,
        'additionalExecutorsCount': 0,
        'executorsToDecline': [],
    }
    endpoint_url = f'https://{host}/admin/overbooking/vacancy'
    r = requests.patch(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text
# print(update_overbooking())


vacancyId = []
with open('D:/WORK/python/list_vacancyId.txt', 'r') as file:
    for line in file:
        vacancyId.append(line.strip())

for p in vacancyId:
    print(update_overbooking(p))
