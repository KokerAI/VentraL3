import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
    host = 'api.dap.ventra.ru/api'

is_archive = True
max_workers = min(32, (os.cpu_count() or 1) * 4)
_log_lock = threading.Lock()
_completed_count = 0  # Глобальный счетчик завершенных проектов


def project_archive(project_id):
    headers = {'Authorization': auth.strip()}
    archive_param = "true" if is_archive else "false"
    endpoint_url = f'https://{host}/admin/projects/archive/{project_id}?archive={archive_param}'
    try:
        r = requests.patch(endpoint_url, headers=headers, timeout=30)
        return project_id, r.status_code, r.text[:100]
    except Exception as e:
        return project_id, None, str(e)[:100]


project_ids = []
with open('D:/WORK/python/list_projectId.txt', 'r') as file:
    for line in file:
        if line.strip():
            project_ids.append(line.strip())

total = len(project_ids)
success_count = error_count = 0
start_time = datetime.now()


def process_project(project_id):
    global _completed_count, success_count, error_count

    project_id, status, response = project_archive(project_id)

    with _log_lock:
        _completed_count += 1
        current_count = _completed_count

        if status and 200 <= status < 300:
            success_count += 1
        else:
            error_count += 1

        print(f"Project ID: {project_id}, Status: {status}, Response: {response}")
        print(f"Сделано {current_count} из {total}. Успешно: {success_count}, Ошибок: {error_count}")

    return status


with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_project, pid) for pid in project_ids]

    for future in as_completed(futures):
        try:
            future.result(timeout=60)
        except Exception as err:
            with _log_lock:
                _completed_count += 1
                current_count = _completed_count
                error_count += 1
                pid = project_ids[
                    len(futures) - len(as_completed(futures))]  # Просто пример, лучше хранить pid в future
                print(f"Thread error for project {pid}: {str(err)[:100]}")
                print(f"Сделано {current_count} из {total}. Успешно: {success_count}, Ошибок: {error_count}")

duration = (datetime.now() - start_time).total_seconds()
print(f"\n✅ Завершено: {success_count}/{total}")
print(f"❌ Ошибок: {error_count}/{total}")
print(f"⏱️ Общее время: {duration:.2f} сек")
print(f"⚡️ Скорость: {total / max(duration, 0.1):.1f} проектов/сек")

progress = int((success_count / total) * 30) if total > 0 else 0
bar = "█" * progress + "░" * (30 - progress)
print(f"📈 Прогресс выполнения: [{bar}] {success_count}/{total}")