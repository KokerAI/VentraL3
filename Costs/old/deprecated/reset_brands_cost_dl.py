import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
host = 'api.dap.ventra.ru/api'

file_path = 'D:/WORK/python/reset_brand_cost.txt'
with open(file_path, 'r') as c:
    lines = [line.strip() for line in c if line.strip()]
total = len(lines)

def reset_brand_cost(brandId, cityGroupId, categoryId):
    headers = {
        'Authorization': auth,
        'accept': '*/*'
    }
    params = {
        'categoryId': categoryId,
        'cityGroupId': cityGroupId,
    }
    endpoint_url = f'https://{host}/admin/costs/v1/brand-costs/{brandId}/rates'
    response = requests.delete(endpoint_url, headers=headers, params=params)
    return response.json(), response.status_code

def process_line(line):
    brandId, cityGroupId, categoryId = line.split("|")
    return reset_brand_cost(brandId, cityGroupId, categoryId)

with ThreadPoolExecutor(max_workers=30) as executor:
    futures = [executor.submit(process_line, line) for line in lines]
    for i, future in enumerate(as_completed(futures), 1):
        print(future.result())
        print(f'Сделано {i} из {total}.')