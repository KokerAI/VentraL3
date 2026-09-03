import requests
import json
# from sql_connect_satge import sql_get_vacancy_in_project

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'


# убрать МЕДкнижку по проектам и заданиям

def get_project_costs(project_id):
    headers = {'Authorization': auth.strip()}
    endpoint_url = f'https://{host}/admin/costs/v1/project-costs/{project_id}'
    r = requests.get(endpoint_url, headers=headers)
    return r.json()


def update_project_costs(new_project_costs):
    headers = {'accept': 'application/json',
               'Authorization': auth.strip(),
               'Content-Type': 'application/json'}
    json_data = new_project_costs
    endpoint_url = f'https://{host}/admin/costs/project-costs/save'
    r = requests.post(endpoint_url, headers=headers, data=json_data)
    return r.status_code


def get_vacancies_cost(vacancies_id):
    headers = {'Authorization': auth.strip()}
    endpoint_url = f'https://{host}/admin/costs/v1/vacancy-costs/{vacancies_id}'
    r = requests.get(endpoint_url, headers=headers)
    return r.json()


def update_vacancies_cost(new_vacancies_cost):
    headers = {'accept': 'application/json',
               'Authorization': auth.strip(),
               'Content-Type': 'application/json'}
    json_data = new_vacancies_cost
    endpoint_url = f'https://{host}/admin/costs/vacancy-costs/save'
    r = requests.post(endpoint_url, headers=headers, data=json_data)
    return r.status_code


def reset_project_rate(project_id):
    project_costs = get_project_costs(project_id)
    headers = {'Authorization': auth.strip()}
    params = {'categoryId': project_costs['categoryId'],
              'cityGroupId': project_costs['cityGroupId']}
    endpoin_url = f'https://{host}/admin/costs/v1/project-costs/{project_id}/rates'
    r = requests.delete(endpoin_url, headers=headers, params=params)
    return r.status_code


def reset_vacancies_rate(vacancies_id):
    vacancies_costs = get_vacancies_cost(vacancies_id)
    headers = {'Authorization': auth.strip()}
    params = {'categoryId': vacancies_costs['categoryId'],
              'cityGroupId': vacancies_costs['cityGroupId']}
    endpoin_url = f'https://{host}/admin/costs/v1/vacancy-costs/{vacancies_id}]/rates'
    r = requests.delete(endpoin_url, headers=headers, params=params)
    return r.status_code


# new_brand_in_project = 232693244
# new_client_id = 200402350
newcityGroupId = [54272]
# newcategoryId = 283858674
project_id = []  # Указываем проекты в котором меняем бренд
with open('D:/WORK/python/list_projectId.txt', 'r') as f:
    for line in f:
        project_id.append(line.strip())
vacancies = []
with open('D:/WORK/python/list_vacancyId.txt', 'r') as f:
    for line in f:
        vacancies.append(line.strip())


for i in project_id:
    project_costs = get_project_costs(i)
    print(i)
    new_project_costs = {'brandId': project_costs['brandId'],
                         'clientId': project_costs['clientId'],
                         'categoryId': project_costs['categoryId'],
                         'rate': project_costs['rates']['executorRate'],
                         'marginality': project_costs['rates']['marginality'],
                         'regionIds': newcityGroupId, #[project_costs['cityGroupId']],
                         'flowType': 'Base',
                         'medBookRequired': project_costs['medBookRequired'],
                         'projectId': i,
                         'timeZone': project_costs['timeZone']}
    # print(new_project_costs)
    print(update_project_costs(json.dumps(new_project_costs)))
    if project_costs['overrideType'] == 'Base':
        reset_project_rate(i)


for i in vacancies:
    vacacies_cost = get_vacancies_cost(i)
    new_vacancies_cost = {'brandId': vacacies_cost['brandId'],
                          'clientId': vacacies_cost['clientId'],
                          'categoryId': vacacies_cost['categoryId'],
                          'rate': vacacies_cost['rates']['executorRate'],
                          'marginality': vacacies_cost['rates']['marginality'],
                          'regionIds': newcityGroupId, #[vacacies_cost['cityGroupId']],
                          'flowType': 'Base',
                          'medBookRequired': vacacies_cost['medBookRequired'],
                          'projectId': vacacies_cost['projectId'],
                          'timeZone': vacacies_cost['timeZone'],
                          'vacancyId': vacacies_cost['vacancyId'],
                          'startTime': vacacies_cost['startTime'],
                          'endTime': vacacies_cost['endTime']}
    print(update_vacancies_cost(json.dumps(new_vacancies_cost)), i)


for i in project_id:
    proj_cost = get_project_costs(i)
    # print(proj_cost)
    print(f'{proj_cost["projectId"]}|{proj_cost["medBookRequired"]}|{proj_cost["cityGroupId"]}')
for i in vacancies:
    vac_cost = get_vacancies_cost(i)
    print(f'{vac_cost["vacancyId"]}|{vac_cost["medBookRequired"]}|{vac_cost["cityGroupId"]}')