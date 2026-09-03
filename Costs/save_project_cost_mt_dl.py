import os
import sys
import threading
import requests
from typing import Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ОБНОВИТЬ СТАВКИ НА ПРОЕКТАХ: project_id|rate|marginality

rate_type = "PerHour"  # perUnit perHour
flow_type = "Base"     # Base Final
auth_file = 'D:/WORK/python/auth.txt'
projects_file = 'D:/WORK/python/save_project_cost.txt'
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


def process_project(line: str, auth_token: str) -> Tuple[str, int, str]:
    """Обрабатывает один проект с валидацией данных."""
    project_id, rate, marginality = line.split('|')
    url = f'https://{host}/admin/costs/v2/project-costs/{project_id}'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Получаем и валидируем настройки проекта
    get_resp = requests.get(url, headers=headers)
    get_resp.raise_for_status()
    project_data = get_resp.json()

    # Безопасное извлечение критичных параметров
    rates_section = project_data.get("rates", {})
    per_hour_rates = rates_section.get("perHourRates", [{}])
    rate_id = per_hour_rates[0].get("id") if per_hour_rates else None
    region_id = rates_section.get("cityGroupId")

    # Формируем полный payload как в рабочем скрипте
    payload = {
        "rateType": rate_type, # perUnit perHour
        "flowType": flow_type, # Base Final
        "marginality": float(marginality),
        "rate": float(rate),
        "categoryId": project_data["categoryId"],
        "medBookRequired": project_data["medBookRequired"],
        "regions": [{"rateId": rate_id, "regionId": region_id}],
        "brandId": project_data["brandId"],
        "clientId": project_data["clientId"],
        "projectId": project_data["projectId"],
        "timeZone": project_data["timeZone"]
    }

    # Выполняем обновление с полными заголовками
    update_url = f'https://{host}/admin/costs/v2/project-costs/save'
    post_resp = requests.post(update_url, headers=headers, json=payload)
    return project_id, post_resp.status_code, post_resp.text


def main():
    auth_token = load_auth()
    with open(projects_file) as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    with ThreadPoolExecutor(max_workers) as executor:
        futures = {executor.submit(process_project, line, auth_token): line for line in lines}

        for i, future in enumerate(as_completed(futures), 1):
            try:
                project_id, status, response = future.result()
                status_msg = f'✅ {project_id} | Статус: {status} | Ответ: {response}...'
            except Exception as e:
                status_msg = f'❌ Ошибка: {str(e)}'

            with lock:
                print(status_msg)
                print(f'Сделано {i} из {total} ({i / total:.1%})')


if __name__ == "__main__":
    main()
