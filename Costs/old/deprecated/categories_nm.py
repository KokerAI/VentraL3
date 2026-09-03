import json
import requests

#     Обновление нескольких ставок по нескольким категориям

with open('D:/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'

'''
categories_id = [283970210]


def get_categories_id(categories_id):
    headers = {'Authorization': auth.strip()}
#    global categories_id
    params = {
        'direction': 'desc',
        'orderBy': 'id',
        'page': '0',
        'size': '20',
        'filter': categories_id,
    }
    endpoint_url = f'https://{host}/admin/categories/paging'
    r = requests.get(endpoint_url, headers=headers, params=params)
    return r.json()


# print(get_categories_id(190308208,190309705))


#for i in categories_id:
#    print(get_categories_id(i)['results'])

for i in categories_id:
    cat_inf = get_categories_id(i)['results']
    for j in cat_inf:
       print(j['id'])

'''


# обновление ставок:   в формате flowType, marginality, rate, regionIds, categoryId, medBookRequired

def update_categories(flowType, marginality, rate, regionIds, categoryId, medBookRequired):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}

    json_data = {
        'flowType': flowType,
        'marginality': marginality,
        'rate': rate,
        'regionIds': [
            regionIds
        ],
        'categoryId': categoryId,
        'medBookRequired': medBookRequired,
    }
    endpoint_url = f'https://{host}/admin/costs/base-costs/save'
    r = requests.post(endpoint_url, headers=headers, json=json_data)
    return r.json()

# print(update_categories('Final',60,202,13786571,190308208,True))

# из файла:

categories_dict = []
with open('D:/python/categories.txt', 'r') as file:
    for line in file:
        flowType, marginality, rate, regionIds, categoryId, medBookRequired = line.strip().split("|")
        print(update_categories(flowType, marginality, rate, regionIds, categoryId, medBookRequired))
        categories_dict.append(categoryId)
category_ids = categories_dict
print(category_ids)

for i in categories_dict:
    cat_inf = get_categories_id(i)['results']
    for j in cat_inf:
       print(j)








