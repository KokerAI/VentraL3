import os
import sys
import threading
import requests
from typing import Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ОБНОВИТЬ СТАВКИ НА ВАКАНСИЯХ: vacancy_id|rate|marginality

rate_type = "PerHour"  # perUnit perHour
flow_type = "Base"     # Base Final
auth_file = 'D:/WORK/python/auth.txt'
vacancies_file = 'D:/WORK/python/save_vacancy_cost.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)
lock = threading.Lock()


def load_auth():
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit("❌ Auth file is empty")
        return token


def process_vacancy(line: str, auth_token: str) -> Tuple[str, int, str]:
    """Обрабатывает вакансию с валидацией данных и безопасным извлечением полей."""
    vacancy_id, rate, marginality = line.split('|')
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Получаем и валидируем настройки вакансии
    settings_url = f'https://{host}/admin/costs/v2/vacancy-costs/{vacancy_id}'
    get_resp = requests.get(settings_url, headers=headers)
    get_resp.raise_for_status()
    vacancy_data = get_resp.json()

    # Безопасное извлечение критичных параметров
    rates_section = vacancy_data.get("rates", {})
    per_hour_rates = rates_section.get("perHourRates", [{}])
    rate_id = per_hour_rates[0].get("id") if per_hour_rates else None
    region_id = rates_section.get("cityGroupId")
    category_id = rates_section.get("categoryId")

    # Формируем полный payload как в рабочем скрипте
    payload = {
        "rateType": rate_type, # perUnit perHour
        "flowType": flow_type, # Base Final
        "marginality": float(marginality),
        "rate": float(rate),
        "categoryId": category_id,
        "regions": [{"rateId": rate_id, "regionId": region_id}],
        "vacancyId": vacancy_id,
        "startTime": vacancy_data["startTime"],
        "endTime": vacancy_data["endTime"],
        "projectId": vacancy_data["projectId"],
        "timeZone": vacancy_data["timeZone"]
    }

    # Выполняем обновление с валидацией
    update_url = f'https://{host}/admin/costs/v2/vacancy-costs/save'
    post_resp = requests.post(update_url, headers=headers, json=payload)
    post_resp.raise_for_status()
    return vacancy_id, post_resp.status_code, post_resp.text


def main():
    auth_token = load_auth()
    with open(vacancies_file) as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    with ThreadPoolExecutor(max_workers) as executor:
        futures = {executor.submit(process_vacancy, line, auth_token): line for line in lines}

        for i, future in enumerate(as_completed(futures), 1):
            try:
                vacancy_id, status, response = future.result()
                status_msg = f'✅ {vacancy_id} | Статус: {status} | Ответ: {response}...'
            except Exception as e:
                status_msg = f'❌ Ошибка: {str(e)}'

            with lock:
                print(status_msg)
                print(f'Сделано {i} из {total} ({i / total:.1%})')


if __name__ == "__main__":
    main()
