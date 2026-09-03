import os
import sys
import threading
import requests
from typing import Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ОБНОВИТЬ СТАВКИ НА БРЕНДАХ: brand_id|categoryId|cityGroupId|medBookRequired|rate|marginality

rate_type = "PerHour"  # perUnit perHour
flow_type = "Final"  # Base Final
auth_file = 'D:/WORK/python/auth.txt'
projects_file = 'D:/WORK/python/save_brands_cost.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)
lock = threading.Lock()


def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit("❌ Auth file is empty")
        return token


def process_brand(line: str, auth_token: str) -> Tuple[str, str, int, str]:
    """Обрабатывает один бренд с валидацией данных"""
    brand_id, categoryId, cityGroupId, medBookRequired, rate, marginality = line.split('|')

    # Получаем текущие настройки бренда
    get_url = (
        f'https://{host}/admin/costs/v2/brand-costs/{brand_id}'
        f'?categoryId={categoryId}&cityGroupIds={cityGroupId}'
    )
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    get_resp = requests.get(get_url, headers=headers, timeout=10)
    get_resp.raise_for_status()
    brand_data = get_resp.json()

    # Безопасное извлечение критичных параметров
    rates = brand_data.get("rates", [])
    target_rate = next((r for r in rates if str(r.get("cityGroupId")) == cityGroupId), None)

    per_hour_rates = (target_rate or {}).get("perHourRates") or []
    rate_id = per_hour_rates[0].get("id") if per_hour_rates else None

    # Формируем полный payload
    payload = {
        "rateType": rate_type,
        "flowType": flow_type,
        "marginality": float(marginality),
        "rate": float(rate),
        "categoryId": categoryId,
        "medBookRequired": medBookRequired.lower() == 'true',
        "regions": [{
            "rateId": rate_id,
            "regionId": cityGroupId
        }],
        "brandId": brand_data["brandId"],
        "clientId": brand_data["clientId"]
    }

    # Выполняем обновление ставки
    post_url = f'https://{host}/admin/costs/v2/brand-costs/save'
    post_resp = requests.post(post_url, headers=headers, json=payload, timeout=10)
    return brand_id, cityGroupId, post_resp.status_code, post_resp.text


def main():
    auth_token = load_auth()
    with open(projects_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    with ThreadPoolExecutor(max_workers) as executor:
        futures = {executor.submit(process_brand, line, auth_token): line for line in lines}

        for i, future in enumerate(as_completed(futures), 1):
            try:
                brand_id, cityGroupId, status, response = future.result()
                status_msg = (
                    f'✅ {brand_id} | Регион: {cityGroupId} | '
                    f'Статус: {status} | Ответ: {response[:100]}...'
                )
            except Exception as e:
                status_msg = f'❌ Ошибка: {str(e)}'

            with lock:
                print(status_msg)
                print(f'📈 Сделано {i} из {total} ({i / total:.1%})\n')


if __name__ == "__main__":
    main()