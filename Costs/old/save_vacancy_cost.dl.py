import os
import sys
import requests
from typing import Dict, Any, Tuple

auth_file = 'D:/WORK/python/auth.txt'
projects_file = 'D:/WORK/python/save_vacancy_cost.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'

# ОБНОВИТЬ СТАВКИ НА ВАКАНСИЯХ: vacancy_id|rate|marginality

def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def fetch_vacancy_settings(vacancyId: str, auth_token: str) -> Dict[str, Any]:
    """Получает настройки проекта через GET-запрос."""
    url = f'https://{host}/admin/costs/v2/vacancy-costs/{vacancyId}'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_vacancy_rate(auth_token: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    """Обновляет ставку проекта через POST-запрос."""
    url = f'https://{host}/admin/costs/v2/vacancy-costs/save'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'

    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


def prepare_payload(vacancy_data: Dict[str, Any], new_rate: str, new_marginality: str) -> Dict[str, Any]:
    """Формирует полный payload для обновления ставки на основе данных проекта."""
    # Извлекаем регион из данных проекта (предполагаем один регион)
    rates_data = vacancy_data.get("rates", {}).get("perHourRates", [{}])[0].get("id")
    region_data = vacancy_data.get("rates", {}).get("cityGroupId")

    return {
        "rateType": "PerHour",  # perUnit perHour
        "flowType": "Base",     # Base Final
        "marginality": float(new_marginality),
        "rate": float(new_rate),
        "regions": [{
            "rateId": rates_data,
            "regionId": region_data
        }],
        "vacancyId": vacancy_data["vacancyId"],
        "startTime": vacancy_data["startTime"],
        "endTime": vacancy_data["endTime"],
        "categoryId": vacancy_data["rates"]["categoryId"],
        "projectId": vacancy_data["projectId"],
        "timeZone": vacancy_data["timeZone"]

    }


def main():
    auth_token = load_auth()
    with open(projects_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    for idx, line in enumerate(lines, 1):
        vacancyId, rate, marginality = line.split('|')

        try:
            vacancy_settings = fetch_vacancy_settings(vacancyId, auth_token)

            payload = prepare_payload(vacancy_settings, rate, marginality)

            # 3. Отправляем обновление
            status, response = update_vacancy_rate(auth_token, payload)

            print(f'✅ {vacancyId} | Статус: {status} | Ответ: {response}...')
            print(f'📈 Сделано {idx} из {total} ({idx / total:.1%})')

        except Exception as e:
            print(f'❌ Ошибка {vacancyId}: {str(e)}')


if __name__ == "__main__":
    main()
