import os
import sys
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Tuple

auth_file = 'D:/WORK/python/auth.txt'
vacancies_file = 'D:/WORK/python/subsidy_vacancy.txt'
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)
lock = threading.Lock()

# ОБНОВИТЬ СТАВКИ НА ВАКАНСИЯХ C СУБСИДИЕЙ: vacancy_id|executor_rate_with_subsidy

def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def fetch_vacancy_cost(vacancy_id: str, auth_token: str) -> Dict[str, Any]:
    """Получает настройки вакансии через GET-запрос."""
    url = f'https://{host}/admin/costs/v2/vacancy-costs/{vacancy_id}'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_vacancy_subsidy(auth_token: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    """Обновляет субсидию вакансии через POST-запрос."""
    url = f'https://{host}/admin/costs/v2/vacancy-costs/save-subsidy'
    headers = {
        'Authorization': auth_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


def prepare_payload(vacancy_data: Dict[str, Any], executor_rate_with_subsidy: str) -> Dict[str, Any]:
    """Формирует payload для обновления субсидии вакансии."""
    rates_data = vacancy_data["rates"]["perHourRates"][0]["id"]
    executor_rate = vacancy_data["rates"]["perHourRates"][0]["executorFinalRate"]
    subsidy_amount = float(executor_rate_with_subsidy) - executor_rate
    return {
        "rateId": rates_data,
        "subsidyAmount": subsidy_amount,
        "vacancyId": vacancy_data["vacancyId"]
    }


def process_line(line: str, auth_token: str, total: int):
    """Обрабатывает одну строку с синхронизацией вывода"""
    vacancy_id, executor_rate_with_subsidy = line.split('|')
    try:
        vacancy_settings = fetch_vacancy_cost(vacancy_id, auth_token)
        payload = prepare_payload(vacancy_settings, executor_rate_with_subsidy)
        status, response = update_vacancy_subsidy(auth_token, payload)

        with lock:
            print(f'✅ {vacancy_id} | Статус: {status} | Ответ: {response[:50]}...')
    except Exception as e:
        with lock:
            print(f'❌ Ошибка {vacancy_id}: {str(e)}')
    finally:
        with lock:
            done = getattr(process_line, 'done', 0) + 1
            setattr(process_line, 'done', done)
            print(f'Сделано {done} из {total} ({done / total:.1%})')


def main():
    auth_token = load_auth()

    with open(vacancies_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        total = len(lines)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_line, line, auth_token, total) for line in lines]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()