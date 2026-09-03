import requests
import json
# from sql_connect_satge import sql_get_vacancy_in_project


# отменить задания

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'

cnt = 1
with open('/del_vac.txt', 'r') as c:
    file_line = sum(1 for line in c)
del_vac_list = []
del_vac_error = []


def get_vacancy_info(vacancy_id):
    headers = {'Authorization': auth.strip()}
    endpoint_url = f'https://{host}/v2/admin/vacancies/{vacancy_id}/'
    r = requests.get(endpoint_url, headers=headers)
    return {'response': r.json(), 'status_code': r.status_code}


def del_vac(vacancy_id):
    headers = {'Authorization': auth.strip()}
    endpoint_url = f'https://{host}/v2/vacancies/cancel/{vacancy_id}/'
    r = requests.patch(endpoint_url, headers=headers)
    return r.json()


with open('D:/WORK/python/del_vac.txt', 'r') as file:
    for line in file:
        vac_info = get_vacancy_info(line.strip())
        print(f'Сделано {cnt} из {file_line}.')
        cnt += 1
        if vac_info['status_code'] == 200:
            if vac_info["response"]["vacancyStatus"] != 'REJECTED':
                if vac_info["response"]["category"]["isFake"] == True:
                    if del_vac(line.strip())['errorCode'] != 200:
                        del_vac_error.append(f'{line.strip()}|{vac_info["response"]["vacancyStatus"]}')
                    del_vac_list.append(vac_info["response"]["id"])
                else:
                    del_vac_error.append(f'{line.strip()}|Fake: {vac_info["response"]["category"]["isFake"]} '
                                         f'internalName: {vac_info["response"]["category"]["internalName"]}')
        else:
            del_vac_error.append(f'{line.strip()}|{vac_info["response"]["message"]}')
print(del_vac_list)
for i in range(0, len(del_vac_error)):
    print(del_vac_error[i])
    
# проверяет на категории isFake и выводит, если они не Fake