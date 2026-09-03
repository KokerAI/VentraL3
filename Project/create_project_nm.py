import requests
import pandas as pd


host = 'api.dap.ventra.ru/api'
# Загрузка данных из Excel
df = pd.read_excel('D:/WORK/python/projects.xlsx')


# Чтение Authorization из файла
with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()

for index, row in df.iterrows():
    # Получение uuid из столбца 'uuid' в Excel файле
    uuid_from_excel = str(row['uuid'])

    payload = {
        "name": str(row['name']),
        "position": {
            "id": int(row['position']),
            "category": {"id": int(row['category'])}
        },
        "address": str(row['address']),
        "preScreening": False,
        "projectShiftConfigs": [
            # {
            #     "endShift": False,
            #     "name": "Без фотографии",
            #     "projectShiftConfig": "WITHOUT_PHOTO",
            #     "startShift": True
            # },
            # {
            #     "endShift": True,
            #     "name": "Без фотографии",
            #     "projectShiftConfig": "WITHOUT_PHOTO",
            #     "startShift": False
            # }
            {"startShift": True, "projectShiftConfig": "PHOTO_EXECUTOR"},
            {"endShift": True, "projectShiftConfig": "PHOTO_EXECUTOR"}
        ],
        "latitude": float(row['latitude']),
        "longitude": float(row['longitude']),
        # "idRequirementDocuments": [0],
        "idRequirementDocuments": [7],
        "person": {
            "gender": str(row['gender']),
            "maxAge": int(row['maxAge']),
            "minAge": int(row['minAge'])
        },
        "numberShop": str(row['numberShop']),
        "brand": {"id": int(row['brand'])},
        "descriptionWizard": {
            "steps": [
                {"position": 0, "type": "Что делать?", "text": "Описание задания"},
                {"position": 1, "type": "Как выйти на задание?", "text": "Записаться в приложении"}
            ]
        }
    }

    headers = {
        "accept": "*/*",
        "uuid": uuid_from_excel,  # Использование uuid из Excel файла
        "Authorization": auth.strip(),
        "Content-Type": "application/json"
    }

    response = requests.post(f"https://{host}/v2/mobile/projects/", json=payload, headers=headers)
    print(payload)

    if response.status_code == 200:
        print(f"Запрос {index} успешно отправлен.")
    else:
        print(f"Ошибка при отправке запроса {index}. Код ошибки: {response.status_code}, {response.text}")
