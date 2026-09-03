import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# ОТМЕНА ВАКАНСИЙ/ЗАДАНИЙ:

def update_vacancies_cancel(vacancies_id):
    headers = {'Authorization': auth.strip()}

    endpoint_url = f'https://{host}/v2/vacancies/cancel/{vacancies_id}/'
    r = requests.patch(endpoint_url, headers=headers)
    return r.status_code, r.text


vacancies_id = []
with open('D:/WORK/python/del_vac.txt', 'r') as file:
    for line in file:
        vacancies_id.append(line.strip())

for p in vacancies_id:
    print(update_vacancies_cancel(p))
