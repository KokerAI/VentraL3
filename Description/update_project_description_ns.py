import json
import requests
import pandas as pd


# with open('D:/python/auth.txt') as f:
#     auth = f.readline()
# host = 'api.stage.dap.ventra.ru/api'
with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


description = pd.read_excel('D:/WORK/python/desc.xlsx',
                            sheet_name='Лист1',
                            index_col='id')

# СТЯНУТЬ ОПИСАНИЕ С КАТЕГОРИЙ НА ПРОЭКТ
cnt = 0


def update_project_description(project_id,
                               additional,
                               details,
                               location,
                               todo,
                               totake,
                               name,
                               phone):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    json_data = {
        'descriptionContent': {
            'additional': additional,
            'details': details,
            'location': location,
            'todo': todo,
            'totake': totake,
            'contacts': {
                'name': name,
                'phone': phone
            }
        }
    }
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    r = requests.patch(url=endpoint_url, headers=headers, json=json_data)
    return r


def get_project_description(project_id):
    headers = {'Authorization': auth.strip()}
    # params = {'projection': 'Project'}
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    r = requests.get(url=endpoint_url, headers=headers)
    descriptionContent = r.json()['descriptionContent']
    return descriptionContent, r.status_code


def get_project_description_clone(project_id):
    headers = {'Authorization': auth.strip()}
    # params = {'projection': 'Project'}
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    r = requests.get(url=endpoint_url, headers=headers)
    descriptionContent = r.json()['descriptionContent']
    return descriptionContent, r.status_code


def get_decs_info_from_cat(cat_id):
    headers = {'Authorization': auth.strip()}
    endpoint_url = f'https://{host}/category/{cat_id}'
    r = requests.get(endpoint_url, headers=headers)
    return r.json()


def get_brand_descrition(**kwargs):
    headers = {'Authorization': auth.strip()}
    params = {'direction': 'desc', 'orderBy': 'id', 'page': '0', 'size': '1000'}
    endpoint_url = f'https://{host}/category/{kwargs["category"]}/description/'
    r = requests.get(endpoint_url, headers=headers, params=params)
    r_desc = r.json()
    r_brand = {}
    for i in r_desc['content']:
        if i['brand']['id'] == kwargs['brand']:
            r_brand = i['description']
    return r_brand


# clone_desc = get_project_description_clone(117039686)[0]
# print(clone_desc['totake'])
# try:
#     desc = get_project_description(93240056)[0]
#     if 'contacts' not in desc:
#         print({'contacts': {'name': '-', 'phone': '-'}})
# except:
#     print({'contacts': {'name': '-', 'phone': '-'}})
# print(clone_desc)
# print(get_decs_info_from_cat(77194004)['descriptionDefaults'])

for prj in description.index.tolist():
    # print(get_project_description(prj)[0])
    try:
        desc_Content = get_project_description(prj)[0]
        if 'contacts' not in desc_Content:
            desc_Content = {'contacts': {'name': '-', 'phone': '-'}}
        # if 'totake' not in desc_Content:
        #     desc_Content['totake'] = '-'
    except:
        desc_Content = {'contacts': {'name': '-', 'phone': '-'}}
    # brand_desc = get_brand_descrition(category=description['category_id'].loc[prj],
    #                                   brand=description['brand_id'].loc[prj])
    # print(brand_desc)
    cat_desc = get_decs_info_from_cat(description['category_id'].loc[prj])['descriptionDefaults']
    # print(cat_desc)
    # print(description['todo'].loc[prj])
    update_project_description(prj,
                               cat_desc['additional'],
                               cat_desc['details'],
                               cat_desc['location'],
                               cat_desc['todo'],
                               cat_desc['totake'],
                               desc_Content['contacts']['name'],
                               desc_Content['contacts']['phone'])
    cnt += 1
    print(f'Проект {prj} обновлён сделано {cnt}')
    # print(f'{prj} with category {description["category"].loc[prj]} done')



# print(get_decs_info_from_cat(85926978)['descriptionDefaults'])

# print(description.index.tolist())
# print(description.loc[101946396].tolist())
# print(json.dumps(description['todo'].loc[101946396], ensure_ascii=False))


