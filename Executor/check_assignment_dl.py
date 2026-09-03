import requests

auth = open('D:/WORK/python/auth.txt').read().strip()
# host = 'api.stage.dap.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# ПРОВЕРКА ПОДХОДИТ ЛИ ИСП ТРЕБОВАНИЯМ ЗАДАНИЯ В ФОРМАТЕ: vacancy_id|executor_id   534849752|323294382

lines = [line.strip() for line in open('D:/WORK/python/list_userId.txt') if '|' in line]

total = len(lines)
count = 0
for line in lines:
    count += 1
    vacancy_id, executor_id = line.split('|')
    url = f"https://{host}/admin/support/assign/vacancy/{vacancy_id}?executorId={executor_id}"

    response = requests.get(url, headers={'accept': 'application/hal+json', 'Authorization': auth})

    print(f"Vacancy {vacancy_id}, Executor {executor_id}: Status: {response.status_code}, Response: {response.text}")
    print(f"Сделано {count} из {total}.")
