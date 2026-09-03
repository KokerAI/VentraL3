import os
import sys
import re
import requests
import psycopg2
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent));from db_config import get_db_config

# ДОБАВЛЕНИЕ ИСПА В МАССОВЫЕ СТОПЛИСТЫ КЛИЕНТОВ ПО phone id uuid ЗА ИСКЛЮЧЕНИЕМ exclude_org_ids = []

# === НАСТРОЙКИ ===
exclude_org_ids = [422745070]  # Исключить блокировку по определенным клиентам через запятую или пусто
process_by = 'phone'           # phone id uuid
enable_log = False             # True False
host = 'api.dap.ventra.ru/api'
# host = 'api.stage.dap.ventra.ru/api'
auth_file = 'D:/WORK/python/auth.txt'
input_file = 'D:/WORK/python/list_userId.txt'
script_name = os.path.basename(__file__)
db_config = get_db_config()  # Динамическая загрузка из .ENV
max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
# max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)

# === ИНИЦИАЛИЗАЦИЯ ===
log_lock = threading.Lock()
_cache = threading.local()
console_lock = threading.Lock()
log_handle = None

# === ЛОГ В ПАПКЕ СКРИПТА ===
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'mass_stoplist_executor.log')


def log_msg(msg: str, err: bool = False):
    """Логирует сообщение в консоль и файл"""
    prefix = "❌ " if err else ""
    with log_lock:
        print(f"{prefix}{msg}")
        if enable_log and log_handle is not None:
            assert log_handle is not None
            log_handle.write(f"{msg}\n")  # type: ignore


def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def normalize_phone(phone: str) -> str:
    """Нормализует номер телефона для поиска в БД"""
    digits = ''.join(c for c in phone if c.isdigit())

    if len(digits) == 11 and digits.startswith('7'):
        return f'+{digits}'
    elif len(digits) == 11 and digits.startswith('8'):
        return f'+7{digits[1:]}'  # Замена 8 на 7
    elif len(digits) == 10 and digits.startswith('9'):
        return f'+7{digits}'
    elif len(digits) >= 10:
        return digits[-10:]  # Последние 10 цифр как базовый номер
    return phone


def is_valid_uuid(uid: str) -> bool:
    """Проверяет валидность UUID"""
    return bool(re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', uid.lower()))


def check_db_connection():
    """Проверяет подключение к БД"""
    try:
        with get_db_connection() as conn:
            conn.cursor().execute("SELECT 1")
    except Exception as e:
        sys.exit(f"\n❌ DB_ERROR: {str(e).split('FATAL:')[-1].strip()}")


def validate_api_connection(auth: str, host: str) -> None:
    """Проверяет соединение с API и валидность токена ДО начала обработки"""
    try:
        resp = requests.get(f"https://{host}/admin/me", headers={"Authorization": auth}, timeout=10)
        if resp.status_code in (401, 403):
            sys.exit(f"❌ FATAL: Invalid token (HTTP {resp.status_code})")
        if not 200 <= resp.status_code < 300:
            sys.exit(f"❌ FATAL: API unavailable (HTTP {resp.status_code})")
        print(f"✅ API validated (HTTP {resp.status_code})")
    except requests.exceptions.RequestException as e:
        sys.exit(f"❌ FATAL: API connection failed: {str(e)}")


def get_db_connection():
    """Создает подключение к БД"""
    return psycopg2.connect(**db_config)


def get_orgs_info():
    """Получает организации для стоплиста"""
    cond = "AND id NOT IN %s" if exclude_org_ids else ""
    query = f"""SELECT id, name, org_id FROM organization WHERE org_id ~ '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-4[0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$'{cond}"""
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(query, (tuple(exclude_org_ids),) if exclude_org_ids else None)
        return cur.fetchall()


def get_exec(ident: str, mode: str) -> tuple[str | None, str]:
    """Получает UUID исполнителя с кэшированием"""
    if not hasattr(_cache, 'exec_cache'):
        _cache.exec_cache = {}
    key = (ident, mode)
    if key in _cache.exec_cache:
        return _cache.exec_cache[key]

    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            if mode == 'phone':
                cur.execute("SELECT uuid, phone FROM users WHERE phone = %s", (normalize_phone(ident),))
            elif mode == 'id':
                cur.execute("SELECT uuid FROM users WHERE id = %s", (int(ident),))
            elif mode == 'uuid' and is_valid_uuid(ident):
                cur.execute("SELECT uuid FROM users WHERE uuid = %s", (ident,))
            else:
                result = (None, ident)
                _cache.exec_cache[key] = result
                return result
            res = cur.fetchone()
            result = (res[0], ident) if res else (None, ident)
    except Exception as e:
        log_msg(f"DB_ERROR({ident}): {str(e)[:100]}", True)
        result = (None, ident)
    _cache.exec_cache[key] = result
    return result


def add_to_stoplist(uuid: str, org_uuid: str, token: str):
    """Добавляет в стоплист"""
    url = f'https://{host}/admin/stoplists/{uuid}/'
    headers = {'Authorization': token}
    try:
        r = requests.post(url, headers=headers, json=[org_uuid], timeout=8)
        return r.status_code, r.text[:100] if r.status_code >= 400 else ""
    except Exception as e:
        return 500, str(e)[:100]


def process_task(task, token):
    """Обрабатывает одну задачу"""
    disp, uuid, oid, oname, ouid = task
    if not uuid:
        return disp, None, oid, oname, ouid, 404, "UUID_NOT_FOUND"
    return *task, *add_to_stoplist(uuid, ouid, token)


# === ОСНОВНОЙ КОД ===
def main():
    """Основная точка входа"""
    global log_handle
    token = load_auth()
    check_db_connection()
    validate_api_connection(token, host)
    start = datetime.now()

    if enable_log:
        log_path = os.path.join(os.path.dirname(__file__), 'mass_stoplist_executor.log')
        log_handle = open(log_path, 'w', buffering=1, encoding='utf-8', errors='replace')
        log_msg(f'# {script_name}, {start.strftime("%Y-%m-%d %H:%M:%S")}')

    with open(input_file, encoding='utf-8') as f:
        idents = [line.strip() for line in f if line.strip()]

    orgs = get_orgs_info()
    tasks = []
    for ident in idents:
        uuid, disp = get_exec(ident, process_by)
        for org in orgs:
            oid, oname, ouid = org
            tasks.append((disp, uuid, oid, oname, ouid))

    ok = total = len(tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futs = [exe.submit(process_task, t, token) for t in tasks]
        for i, fut in enumerate(as_completed(futs), 1):
            disp, uuid, oid, oname, ouid, status, resp = fut.result()

            if status == 200:
                msg = f"✅ Executor: {disp}, Org_uuid: {ouid}, Org_id: {oid}, Org_name: {oname}"
            else:
                ok -= 1
                error_type = "UUID_NOT_FOUND" if status == 404 else f"HTTP_{status}"
                msg = f"❌ Executor {disp} → {error_type}: {resp[:200]}"

            output = f"Сделано {i} из {total}.\n{msg}"
            with console_lock:
                print(output)
            if enable_log and log_handle:
                with log_lock:
                    log_handle.write(output + '\n')

    duration = (datetime.now() - start).total_seconds()
    summary = (
        f"\n\nСтатистика:\n"
        f"✅ Успешно: {ok}/{total}\n"
        f"❌ Ошибок: {total - ok}\n"
        f"⚡️ Скорость: {total / max(0.1, duration):.1f} операций/сек\n"
        f"⏱️ Время: {duration:.1f} сек"
    )
    with console_lock:
        print(summary)
    if enable_log and log_handle:
        with log_lock:
            log_handle.write(summary + '\n')
        try:
            log_handle.close()
        except Exception as e:
            # Резервный вывод в консоль при ошибке закрытия
            with console_lock:
                print(f"⚠️ Ошибка закрытия лога: {str(e)[:100]}")


if __name__ == "__main__":
    main()
