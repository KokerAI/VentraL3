import requests
from urllib.parse import quote

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
# host = 'api.stage.ventra.ru/api'
host = 'api.dap.ventra.ru/api'

# Для удаления испов из файла в формате: phone   79997777777

def executor_delete (phone):
    headers = {'Authorization': auth.strip(), 'accept': '*/*'}
    encoded_phone = quote("+" + phone)
    endpoint_url = f'https://{host}/admin/support/user/{encoded_phone}'
    r = requests.delete(endpoint_url, headers=headers)
    return r.status_code, r.text

cnt = 0
with open('D:/WORK/python/list_userId.txt', 'r', encoding='utf-8') as c:
    file_line = sum(1 for line in c)

with open('D:/WORK/python/list_userId.txt', 'r', encoding='utf-8') as c:
    for line in c:
        phone = line.strip()
        status, response = executor_delete(phone)
        print (f'Phone: {phone}, Status: {status}, Response: {response}')
        cnt += 1
        print(f'Сделано {cnt} из {file_line}.')