import requests

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

cnt = 0
with open('D:/WORK/python/save_brands_cost.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)


# Обновить ставку по брендам:    clientId, brandId, regionIds, categoryId, rate, marginality, medBookRequired
# ПРОВЕРЯТЬ flowType БАЗОВАЯ ИЛИ КЛИЕНТСКАЯ !!!

def update_brands_cost (clientId, brandId, regionIds, categoryId, rate, marginality, medBookRequired):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'flowType': 'Base',  # Final  Base
        'marginality': marginality,
        'rate': rate,
        'regionIds': [
            regionIds,
        ],
        'categoryId': categoryId,
        'medBookRequired': medBookRequired,  # True False
        'brandId': brandId,
        'clientId': clientId,
    }

    endpoint_url = f'https://{host}/admin/costs/brand-costs/save'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.status_code, r.text


with open('D:/WORK/python/save_brands_cost.txt', 'r', encoding='utf-8') as c:
    for line in c:
        cnt += 1
        clientId, brandId, regionIds, categoryId, rate, marginality, medBookRequired = line.strip().split("|")
        print(update_brands_cost(clientId, brandId, regionIds, categoryId, rate, marginality, medBookRequired))
        print(f'Сделано {cnt} из {file_line}.')
