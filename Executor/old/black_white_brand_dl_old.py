import requests
from datetime import datetime, timezone
import time

# Чтение авторизации
auth = open('D:/WORK/python/auth.txt').read().strip()

# BASE_URL = 'https://api.stage.dap.ventra.ru/api//v1/brands/save'
BASE_URL = 'https://api.dap.ventra.ru/api/v1/brands/save'

# Чтение списков
brand_ids = [line.strip() for line in open('D:/WORK/python/list_brandId.txt') if line.strip().isdigit()]
executor_ids = [line.strip() for line in open('D:/WORK/python/list_userId.txt') if line.strip().isdigit()]

if not brand_ids or not executor_ids:
    print("Ошибка: не найдены корректные ID в файлах")
    exit(1)

total = len(executor_ids) * len(brand_ids)
cnt = 0

# Создаем сессию для повторного использования соединения
session = requests.Session()
session.headers.update({
    'accept': 'application/hal+json',
    'Content-Type': 'application/json',
    'Authorization': auth
})

# Основной цикл - обрабатываем каждый запрос сразу
for executor_id in executor_ids:
    for brand_id in brand_ids:
        cnt += 1
        # Новая сессия и обновление токена каждые 20000 запросов (если обработка занимает больше времени жизни токена)
        if cnt % 20000 == 1:
            with open('/auth.txt', 'r') as f:
                auth = f.read().strip()  # Обновление актуального токена
            session = requests.Session()
            session.headers.update({
                'accept': 'application/hal+json',
                'Content-Type': 'application/json',
                'Authorization': auth
            })

        try:
            # Формируем данные для запроса
            json_data = {
                "brandId": int(brand_id),
                "executorId": int(executor_id),
                "brandListStatus": "Processed",  # Processed Deleted
                # "startTime": "2024-11-20T21:21:46Z"
                "startTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                # "endtTime": "2024-11-20T21:21:46Z"  # Протестировать
            }
            # Отправляем запрос
            response = session.post(BASE_URL, json=json_data, timeout=10)

            # Выводим результат сразу
            is_success = 200 <= response.status_code < 300
            status = "УСПЕХ" if is_success else "ОШИБКА"
            print(f"[{status}] Executor: {executor_id}, Brand: {brand_id}, Status: {response.status_code}")

            if is_success:
                print(f"Response: {response.text}")
            else:
                print(f"Error: {response.text}")

            print(f"Сделано {cnt} из {total}\n")

        except Exception as e:
            print(f"Ошибка ({executor_id}, {brand_id}): {str(e)}")
            print(f"Сделано {cnt} из {total}\n")
