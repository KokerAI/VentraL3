import os
import sys
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# === НАСТРОЙКИ ===
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
auth_file = 'D:/WORK/python/auth.txt'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)


def update_description_defaults(category_id):
    """Обновляет описание категории"""
    category_data = get_description_defaults(category_id)

    # Создаем descriptionDefaults если его нет (обязательно)
    if 'descriptionDefaults' not in category_data:
        category_data['descriptionDefaults'] = {}

    '''
    additional Полезные материалы
    details    Как одеться что с собой
    location   Особенности задания
    totake     Как найти и во сколько быть
    todo       Что делать
    '''

    # РАЗДЕЛ И СТРОКА ('НАЧАЛО \n', '\n КОНЕЦ')
    part = 'location'
    line = '🔴ДЛЯ ВЫПОЛНЕНИЯ ЗАДАНИЯ НЕОБХОДИМО БЫТЬ САМОЗАНЯТЫМ'

    # ПОЛНАЯ ПЕРЕЗАПИСЬ НЕОБХОДИМОГО РАЗДЕЛА (РАСКОММЕНТИРОВАТЬ НУЖНОЕ)
    # category_data['descriptionDefaults']['additional'] =
    # category_data['descriptionDefaults']['details'] =
    # category_data['descriptionDefaults']['location'] =
    # category_data['descriptionDefaults']['todo'] =
    # category_data['descriptionDefaults']['totake'] =


    # === СТРОКУ В НАЧАЛО, УКАЗАТЬ PART И LINE (РАЗДЕЛ И СТРОКА) ===
    # description_defaults = category_data['descriptionDefaults']
    # current = description_defaults.get(part, '')
    # if not has_content(description_defaults, part):  # если не хотим добавлять строку в пустой блок
    #     return 0, "skipped: empty description (no other content)"
    # cleaned = current.replace(line, '').lstrip('\n\r')
    # description_defaults[part] = f"{line}\n{cleaned}" if cleaned else line

    # === СТРОКУ В КОНЕЦ, УКАЗАТЬ PART И LINE (РАЗДЕЛ И СТРОКА) ===
    # description_defaults = category_data['descriptionDefaults']
    # current = description_defaults.get(part, '')
    # if not has_content(description_defaults, part):  # если не хотим добавлять строку в пустой блок
    #     return 0, "skipped: empty description (no other content)"
    # cleaned = current.replace(line, '').rstrip('\n\r')
    # description_defaults[part] = f"{cleaned}\n{line}" if cleaned else line

    # === УДАЛЕНИЕ СТРОКИ, УКАЗАТЬ PART И LINE (РАЗДЕЛ И СТРОКА) ===
    # description_defaults = category_data.get('descriptionDefaults', {})
    # current = description_defaults.get(part, '')
    # clean_line = line.strip()
    # description_defaults[part] = current.replace(clean_line, '').strip('\n\r')
    # category_data['descriptionDefaults'] = description_defaults

    headers = {
        'Authorization': load_auth(auth_file),
        'accept': '*/*',
        'content-type': 'application/json'
    }

    # Эндпоинт для обновления данных проекта
    endpoint_url = f'https://{host}/category/'
    # Отправляем обновленные данные
    r = requests.put(endpoint_url, headers=headers, json=category_data)
    return r


def load_auth(auth_file):
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        return f.readline().strip()


def get_description_defaults(category_id):
    """Получает описание категории"""
    headers = {'Authorization': load_auth(auth_file), 'accept': '*/*'}
    endpoint_url = f'https://{host}/category/{category_id}'
    r = requests.get(endpoint_url, headers=headers)
    return r.json()


def has_content(desc, current_part):
    """Проверяет, существует ли описание"""
    if desc.get(current_part, '').strip():
        return True
    return any(desc.get(p, '').strip() for p in ['additional', 'details', 'location', 'todo', 'totake'])


categoryId = []
with open('D:/WORK/python/list_categoryId.txt', 'r') as file:
    for line in file:
        categoryId.append(line.strip())

total = len(categoryId)

# === МНОГОПОТОЧНАЯ ОБРАБОТКА КАТЕГОРИЙ ===
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Подготовка задач
    futures = {executor.submit(update_description_defaults, c): c for c in categoryId}

    # Обработка результатов
    for i, future in enumerate(as_completed(futures), 1):
        c = futures[future]
        try:
            r = future.result()
            print(f'Category {c}, Status: {r.status_code}, Response: {r.text}')
        except Exception as e:
            print(f'Category {c}, Error: {str(e)}')

        print(f"Сделано {i} из {total}.")


''' СТАРАЯ ПРОВЕРКА НАЛИЧИЯ ОПИСАНИЯ (ПРОВЕРЯЕТ ТОЛЬКО ИЗМЕНЯЕМЫЙ БЛОК)
    if not current.strip():  # если не хотим добавлять строку в пустой блок
        return 0, "skipped: empty description"
'''


''' СТАРЫЙ ЦИКЛ ПРОЦЕССИНГА
cnt = 0

for c in categoryId:
    status, response = update_description_defaults(c)
    print(f'Category {c}: Status: {status}, Response: {response}')
    cnt += 1
    print(f"Сделано {cnt} из {total}.")
'''

''' ВСЕ ПЕРЕДАВАЕМЫЕ ПОЛЯ
json_data = {
    "byDefault": False,
    "confirmationCondition": "MANUALLY",
    "createdOn": "2025-10-17T08:46:33.750Z",
    "descriptionDefaults": {
        "additional": "",
        "location": "",
        "details": "",
        "todo": " ",
        "totake": "",
        "useDefaults": False
    },
    "documents": [],
    "internalName": "раб зала_Аш К1",
    "status": "ACTIVE",
    "visibleStatus": "VISIBLY",
    "groups": [],
    "isProcessingCategory": False,
    "id": category_id,
    "name": "__тест",
    "description": "тест",
    "isFake": False,
    "longTempo": False,
    "isInternship": False,
    "useCategoryProviderInn": False
}
DESCRIPTION DEFAULTS
    category_data['descriptionDefaults'] = {
        "additional": "",
        "location": "",
        "details": "",
        "todo": "",
        "totake": "",
        "useDefaults": False
    }
'''
