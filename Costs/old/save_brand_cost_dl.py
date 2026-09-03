import os
import sys
from typing import Dict, Any, Tuple
import requests

# ОБНОВИТЬ СТАВКИ НА БРЕНДАХ: brand_id|categoryId|cityGroupId|medBookRequired|rate|marginality

rate_type = "PerHour"  # perUnit perHour
flow_type = "Final"     # Base Final
auth_file = 'D:/WORK/python/auth.txt'
projects_file = 'D:/WORK/python/save_brands_cost.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'


def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def fetch_brand_rate(brand_id: str, categoryId: str, cityGroupId: str, auth_token: str) -> Dict[str, Any]:
    """Получает настройки проекта через GET-запрос."""
    url = f'https://{host}/admin/costs/v2/brand-costs/{brand_id}?categoryId={categoryId}&cityGroupIds={cityGroupId}'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_brand_rate(auth_token: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    """Обновляет ставку проекта через POST-запрос."""
    url = f'https://{host}/admin/costs/v2/brand-costs/save'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'

    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


def prepare_payload(project_data: Dict[str, Any], categoryId: str, cityGroupId: str, medBookRequired: str, new_rate: str, new_marginality: str) -> Dict[str, Any]:
    rates = project_data.get("rates", [])
    rate = next((r for r in rates if r.get("cityGroupId") == cityGroupId), None)
    per_hour_rates = (rate or {}).get("perHourRates") or []
    rates_data = per_hour_rates[0].get("id") if per_hour_rates else None

    return {
        "rateType": rate_type,  # perUnit perHour
        "flowType": flow_type,   # Base Final
        "marginality": float(new_marginality),
        "rate": float(new_rate),
        "categoryId": categoryId,
        "medBookRequired": medBookRequired,
        "regions": [{
            "rateId": rates_data,
            "regionId": cityGroupId
        }],
        "brandId": project_data["brandId"],
        "clientId": project_data["clientId"]
    }


def main():
    auth_token = load_auth()
    with open(projects_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    for idx, line in enumerate(lines, 1):
        (brand_id, categoryId, cityGroupId, medBookRequired, rate, marginality) = line.split('|')

        try:
            brand_settings = fetch_brand_rate(brand_id, categoryId, cityGroupId, auth_token)

            payload = prepare_payload(brand_settings, categoryId, cityGroupId, medBookRequired, rate,
                                      marginality)

            # 3. Отправляем обновление
            status, response = update_brand_rate(auth_token, payload)

            print(f'✅ {brand_id} | Статус: {status} | Ответ: {response}...')
            print(f'📈 Сделано {idx} из {total} ({idx / total:.1%})')

        except Exception as e:
            print(f'❌ Ошибка {brand_id}: {str(e)}')


if __name__ == "__main__":
    main()
