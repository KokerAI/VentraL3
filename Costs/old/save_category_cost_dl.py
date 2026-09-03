import os
import sys
from typing import Dict, Any, Tuple

import requests

auth_file = 'D:/WORK/python/auth.txt'
projects_file = 'D:/WORK/python/save_category_cost.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'

# ОБНОВИТЬ СТАВКИ НА КАТЕГОРИЯХ: categoryId|cityGroupId|medBookRequired|new_rate|new_marginality

def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def fetch_category_rate(categoryId: str, auth_token: str) -> Dict[str, Any]:
    """Получает настройки проекта через GET-запрос."""
    url = f'https://{host}/admin/costs/v2/base-costs?categoryId={categoryId}'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_category_rate(auth_token: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    """Обновляет ставку проекта через POST-запрос."""
    url = f'https://{host}/admin/costs/v2/base-costs/save'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'

    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


def prepare_payload(project_data: Dict[str, Any], categoryId: str, cityGroupId: str, medBookRequired: str,  new_rate: str, new_marginality: str) -> Dict[str, Any]:
    rates = project_data.get("rates", [])
    rate = next((r for r in rates if r.get("cityGroupId") == cityGroupId), None)

    per_hour_rates = (rate or {}).get("perHourRates") or []
    rates_data = per_hour_rates[0].get("id") if per_hour_rates else None

    return {
        "rateType": "PerHour",
        "flowType": 'Base',  # Base Final
        "marginality": float(new_marginality),
        "rate": float(new_rate),
        "categoryId": categoryId,
        "medBookRequired": medBookRequired,
        "regions": [{
            "rateId": rates_data,
            "regionId": cityGroupId
        }]
    }



def main():
    auth_token = load_auth()
    with open(projects_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    for idx, line in enumerate(lines, 1):
        (categoryId, cityGroupId, medBookRequired, rate, marginality) = line.split('|')

        try:
            category_settings = fetch_category_rate(categoryId, auth_token)

            payload = prepare_payload(category_settings, categoryId, cityGroupId, medBookRequired, rate, marginality)

            # 3. Отправляем обновление
            status, response = update_category_rate(auth_token, payload)

            print(f'✅ {categoryId} city_group: {cityGroupId} | Статус: {status} | Ответ: {response}...')
            print(f'📈 Сделано {idx} из {total} ({idx / total:.1%})')

        except Exception as e:
            print(f'❌ Ошибка {categoryId}: {str(e)}')


if __name__ == "__main__":
    main()