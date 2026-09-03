import os
import sys
import requests
from typing import Dict, Any, Tuple

auth_file = 'D:/WORK/python/auth.txt'
projects_file = 'D:/WORK/python/subsidy_project.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'

# ОБНОВИТЬ СТАВКИ НА ПРОЕКТАХ C СУБСИДИЕЙ: project_id|executor_rate_with_subsidy

def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def fetch_project_cost(project_id: str, auth_token: str) -> Dict[str, Any]:
    """Получает настройки проекта через GET-запрос."""
    url = f'https://{host}/admin/costs/v2/project-costs/{project_id}'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_project_subsidy(auth_token: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    """Обновляет ставку проекта через POST-запрос."""
    url = f'https://{host}/admin/costs/v2/project-costs/save-subsidy'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'

    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


def prepare_payload(project_data: Dict[str, Any], executor_rate_with_subsidy: str) -> Dict[str, Any]:
    """Формирует полный payload для обновления ставки на основе данных проекта."""
    rates_data = project_data.get("rates", {}).get("perHourRates",  [{}])[0].get("id")
    executor_rate = project_data.get("rates", {}).get("perHourRates",  [{}])[0].get("executorFinalRate")
    subsidy_amount = float(executor_rate_with_subsidy) - executor_rate
    return {
        "rateId": rates_data,
        "subsidyAmount": subsidy_amount,
        "projectId": project_data["projectId"]
    }


def main():
    auth_token = load_auth()
    with open(projects_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    for idx, line in enumerate(lines, 1):
        project_id, executor_rate_with_subsidy = line.split('|')

        try:
            project_settings = fetch_project_cost(project_id, auth_token)

            payload = prepare_payload(project_settings, executor_rate_with_subsidy)

            # 3. Отправляем обновление
            status, response = update_project_subsidy(auth_token, payload)

            print(f'✅ {project_id} | Статус: {status} | Ответ: {response}...')
            print(f'Сделано {idx} из {total} ({idx / total:.1%})')

        except Exception as e:
            print(f'❌ Ошибка {project_id}: {str(e)}')


if __name__ == "__main__":
    main()