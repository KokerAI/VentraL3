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


def update_description_content(project_id):
    """Обновляет описание проекта"""
    project_data = get_description_content(project_id)

    # Создаем descriptionContent если его нет (не трогать без необходимости)
    # if 'descriptionContent' not in project_data:
    #     project_data['descriptionContent'] = {}

    '''
    additional Полезные материалы
    details    Как одеться что с собой
    location   Особенности задания
    totake     Как найти и во сколько быть
    todo       Что делать
    contacts   Контакты
    '''

    # РАЗДЕЛ И СТРОКА ('НАЧАЛО \n', '\n КОНЕЦ')
    part = 'location'
    line = '🔴ДЛЯ ВЫПОЛНЕНИЯ ЗАДАНИЯ НЕОБХОДИМО БЫТЬ САМОЗАНЯТЫМ'

    # ПОЛНАЯ ПЕРЕЗАПИСЬ НЕОБХОДИМОГО РАЗДЕЛА (РАСКОММЕНТИРОВАТЬ НУЖНОЕ)
    # project_data['descriptionContent']['additional'] =
    # project_data['descriptionContent']['details'] =
    # project_data['descriptionContent']['location'] =
    # project_data['descriptionContent']['todo'] =
    # project_data['descriptionContent']['totake'] =
    # project_data['descriptionContent']['contacts'] = { 'name': '', 'phone': ''}

    # === СТРОКУ В НАЧАЛО, УКАЗАТЬ PART И LINE (РАЗДЕЛ И СТРОКА) ===
    # description_content = project_data.get('descriptionContent', {})
    # current = description_content.get(part, '')
    # if not has_content(description_content, part):  # если не хотим добавлять строку в пустой блок
    #     return 0, "skipped: empty description (no other content)"
    # cleaned = current.replace(line, '').lstrip('\n\r')
    # description_content[part] = f"{line}\n{cleaned}" if cleaned else line

    # === СТРОКУ В КОНЕЦ, УКАЗАТЬ PART И LINE (РАЗДЕЛ И СТРОКА) ===
    # description_content = project_data.get('descriptionContent', {})
    # current = description_content.get(part, '')
    # if not has_content(description_content, part):  # если не хотим добавлять строку в пустой блок
    #     return 0, "skipped: empty description (no other content)"
    # cleaned = current.replace(line, '').rstrip('\n\r')
    # description_content[part] = f"{cleaned}\n{line}" if cleaned else line

    # === УДАЛЕНИЕ СТРОКИ, УКАЗАТЬ PART И LINE (РАЗДЕЛ И СТРОКА) ===
    # description_content = project_data.get('descriptionContent', {})
    # current = description_content.get(part, '')
    # clean_line = line.strip()
    # description_content[part] = current.replace(clean_line, '').strip('\n\r')
    # project_data['descriptionContent'] = description_content

    headers = {
        'Authorization': load_auth(auth_file),
        'accept': '*/*',
        'Content-Type': 'application/json'
    }

    # Эндпоинт для обновления данных проекта
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    # Отправляем обновленные данные
    r = requests.patch(endpoint_url, headers=headers, data=json.dumps(project_data))
    return r.status_code


def load_auth(auth_file):
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        return f.readline().strip()


def get_description_content(project_id):
    """Получает описание проекта"""
    headers = {'Authorization': load_auth(auth_file), 'accept': '*/*'}
    endpoint_url = f'https://{host}/admin/projects/{project_id}'
    r = requests.get(endpoint_url, headers=headers)
    return r.json()


def has_content(desc, current_part):
    """Проверяет, существует ли описание"""
    if desc.get(current_part, '').strip():
        return True
    return any(desc.get(p, '').strip() for p in ['additional', 'details', 'location', 'todo', 'totake'])


projectId = []
with open('D:/WORK/python/list_projectId.txt', 'r') as file:
    for line in file:
        projectId.append(line.strip())

total = len(projectId)

# === МНОГОПОТОЧНАЯ ОБРАБОТКА ПРОЕКТОВ ===
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Подготовка задач
    futures = {executor.submit(update_description_content, p): p for p in projectId}

    # Обработка результатов
    for i, future in enumerate(as_completed(futures), 1):
        p = futures[future]
        try:
            status_code = future.result()
            print(f'Project {p}, Status: {status_code}')
        except Exception as e:
            print(f'Project {p}, Error: {str(e)}')

        print(f"Сделано {i} из {total}.")


''' СТАРАЯ ПРОВЕРКА НАЛИЧИЯ ОПИСАНИЯ (ПРОВЕРЯЕТ ТОЛЬКО ИЗМЕНЯЕМЫЙ БЛОК)
    if not current.strip():  # если не хотим добавлять строку в пустой блок
        return 0, "skipped: empty description"
'''