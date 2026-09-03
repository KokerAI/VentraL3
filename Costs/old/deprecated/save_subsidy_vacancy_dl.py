import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

cnt = 0
with open('D:/WORK/python/save_subsidy_vacancy.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


# Обновить субсидии по проекту:    vacancyId, executorRateWithSubsidy
#

def save_subsidy_vacancy(vacancyId, executorRateWithSubsidy):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'executorRateWithSubsidy': executorRateWithSubsidy,
        'vacancyId': vacancyId,
    }

    endpoint_url = f'https://{host}/admin/costs/vacancy-costs/save-subsidy'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/save_subsidy_vacancy.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        vacancyId, executorRateWithSubsidy = line.strip().split("|")
        print(vacancyId, save_subsidy_vacancy(vacancyId, executorRateWithSubsidy))
        print(f'Сделано {cnt} из {file_line}.')
