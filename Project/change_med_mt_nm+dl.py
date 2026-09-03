import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline()
host = 'api.dap.ventra.ru/api'
lock = threading.Lock()
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)


# true false
def change_project_med(project_id):
    headers = {'Authorization': auth.strip()}
    params = {
        'update-vacancies': 'true',
        'update-activities': 'false',
        'medbook': 'false',
    }
    endpoint_url = f'https://{host}/admin/support/change-project-med/{project_id}'
    r = requests.post(endpoint_url, headers=headers, params=params)
    return project_id, r.status_code, r.text


project_ids = []
with open('D:/WORK/python/list_projectId.txt', 'r') as file:
    for line in file:
        project_ids.append(line.strip())

total = len(project_ids)
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(change_project_med, pid) for pid in project_ids]

    for i, future in enumerate(as_completed(futures), 1):
        try:
            pid, status, response = future.result()
            with lock:
                print(f'✅ Project {pid} | Status: {status} | Response: {response}')
        except Exception as e:
            pid = future.result()[0] if future.done() else "Unknown"
            with lock:
                print(f'❌ Error for {pid}: {str(e)}')
        finally:
            with lock:
                print(f'Сделано {i} из {total}')