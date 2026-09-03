import os
import sys
import time
import requests
import psycopg2
import pandas as pd
import threading
from enum import Enum
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА - ВКЛЮЧИТЬ ЭТОТ ИМПОРТ, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent)); from db_config import get_db_config

# Создание проектов из файла projects.xlsx

# === КОНФИГ ПРОЕКТА: True False
required_documents = []         # Требования по докам
prescreening = False            # Прескрининг
start_shift  = True             # Фото начало
end_shift    = True             # Фото конец
start_photo  = 'PHOTO_EXECUTOR' # PHOTO_EXECUTOR PHOTO_WITH_NAME WITHOUT_PHOTO
end_photo    = 'PHOTO_EXECUTOR'
start_name   = ''               # Селфи Без_фотографии
end_name     = ''

# === НАСТРОЙКИ ===
process_by   = 'phone'          # phone id uuid
enable_log   = True             # True False
host         = 'api.dap.ventra.ru/api'
# host       = 'api.stage.dap.ventra.ru/api'
auth_file    = 'D:/WORK/python/auth.txt'
input_file   = 'D:/WORK/python/projects.xlsx'
script_name  = os.path.basename(__file__)
# max_workers = min(100, max(4, (os.cpu_count() or 1) * 8))  # Потоки по умолчанию (Корректируется само под CPU)
max_workers = min(32, max(4, (os.cpu_count() or 1) * 4))  # Потоки по умолчанию (Корректируется само под CPU)
db_config = get_db_config()  # Динамическая загрузка из .ENV

# === БАЗА ДАННЫХ ===
# db_config = {
#     'host': 'prod-dap-db1.msk.ventrago.dev',
#     'port': 5432,
#     # 'host'    = 'stage-db1.msk.ventrago.dev'
#     # 'dbname'    = 'stage'
#     'dbname': 'production',
#     'user': 'user',
#     'password': 'password',
# }


# Проверка требуемых библиотек
required_libs = ['pandas', 'requests', 'psycopg2', 'threading', 'datetime']
for lib in required_libs:
    try:
        __import__(lib)
    except ImportError:
        sys.exit(f"❌ Required library '{lib}' is missing. Install with: pip install {lib}")


# === ИНИЦИАЛИЗАЦИЯ ===
class ApiErrorType(Enum):
    AUTH = "AUTH"  # 401/403 - критические
    SERVER = "SERVER"  # 5xx - критические после N попыток
    CLIENT = "CLIENT"  # 400/404 - некритичные
    NETWORK = "NETWORK"  # Таймауты/соединение


# === ЛОГ В ПАПКЕ СКРИПТА ===
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'create_project.log')

# === ЛОГ ПО АБСОЛЮТНОМУ ПУТИ ===
# log_file = 'D:/WORK/python/log.log'
# log_dir = os.path.dirname(log_file)
# if not os.path.exists(log_dir):
#     os.makedirs(log_dir)


ABORT_FLAG = threading.Event()  # Флаг для глобальной остановки при критических ошибках
_log_lock = threading.Lock()  # Блокировка для потокобезопасной записи в лог
_cache = threading.local()  # Потокобезопасный кэш
_db_connections = threading.local()  # Пул соединений с БД на поток


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def normalize_phone(phone):
    """Нормализует номер телефона для поиска в БД"""
    if not phone or pd.isna(phone):
        return None

    if isinstance(phone, (int, float)):
        phone = str(int(phone))
    elif isinstance(phone, str):
        phone = phone.strip()
    else:
        return None

    digits = ''.join(c for c in phone if c.isdigit())

    if len(digits) == 11 and digits.startswith('7'):
        return f'+{digits}'
    elif len(digits) == 11 and digits.startswith('8'):
        return f'+7{digits[1:]}'  # Замена 8 на 7
    elif len(digits) == 10 and digits.startswith('9'):
        return f'+7{digits}'
    elif len(digits) >= 10:
        return digits[-10:]  # Последние 10 цифр как базовый номер
    return phone  # Исходный формат, если не можем нормализовать


def load_auth() -> str:
    """Загружает токен авторизации из файла"""
    if not os.path.exists(auth_file):
        sys.exit(f"❌ Auth file missing: {auth_file}")
    with open(auth_file) as f:
        token = f.readline().strip()
        if not token:
            sys.exit(f"❌ Auth file is empty: {auth_file}")
        return token


def safe_float(value):
    """Безопасное преобразование в float"""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_valid_int(value):
    """Безопасное преобразование в int"""
    if value is None or pd.isna(value):
        return None
    try:
        value_str = str(value).strip()
        if value_str == '':
            return None
        return int(float(value_str))
    except (ValueError, TypeError):
        return None


def is_valid_uuid(uuid_str):
    """Строгая валидация UUID"""
    if not uuid_str:
        return False
    uuid_str = str(uuid_str).strip()
    if len(uuid_str) != 36:
        return False
    parts = uuid_str.split('-')
    if len(parts) != 5:
        return False
    lengths = [8, 4, 4, 4, 12]
    if not all(len(part) == lengths[i] for i, part in enumerate(parts)):
        return False
    hex_chars = set('0123456789abcdefABCDEF')
    return all(c in hex_chars for c in uuid_str.replace('-', ''))


def is_valid_value(value):
    """Проверка валидности значения"""
    if value is None or pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() not in ['nan', 'null', '']
    return True

# === КЭШИРОВАНИЕ И ПУЛ СОЕДИНЕНИЙ ===
def get_db_connection():
    """Возвращает соединение с БД из пула текущего потока"""
    if not hasattr(_db_connections, 'connection') or _db_connections.connection.closed:
        _db_connections.connection = psycopg2.connect(connect_timeout=10, **db_config)
    return _db_connections.connection


def close_db_connection():
    """Закрывает соединение с БД для текущего потока"""
    if hasattr(_db_connections, 'connection') and not _db_connections.connection.closed:
        _db_connections.connection.close()
        del _db_connections.connection


def cached_db_query(key, query, params=None, fetch_one=False):
    """Выполняет запрос с кэшированием результатов для текущего потока"""
    # Инициализация кэша для потока, если еще не создан
    if not hasattr(_cache, 'data'):
        _cache.data = {}

    # Проверка наличия данных в кэше
    if key in _cache.data:
        return _cache.data[key]

    # Выполнение запроса
    try:
        with get_db_connection().cursor() as cur:
            cur.execute(query, params or ())
            result = cur.fetchone() if fetch_one else cur.fetchall()
        # Сохранение в кэш
        _cache.data[key] = result
        return result
    except Exception as e:
        print(f"⚠️ DB query error in cached_db_query: {str(e)[:100]}")
        return None if fetch_one else []


# === РАБОТА С БАЗОЙ ДАННЫХ ===
def check_db_connection():
    """Проверяет подключение к БД и прерывает выполнение при ошибке"""
    try:
        with get_db_connection().cursor() as cur:
            cur.execute("SELECT 1")
        print("✅ Database connection OK")
    except Exception as e:
        error_text = str(e)
        error_parts = error_text.split("FATAL:", 1)
        error_msg = error_parts[1].strip() if len(error_parts) > 1 else error_text
        sys.exit(f"\n❌ DB error: {error_msg}\n")


def execute_db_query(query, params=None, fetch_one=False):
    """Выполняет запрос к БД"""
    try:
        with get_db_connection().cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone() if fetch_one else cur.fetchall()
    except Exception as e:
        print(f"⚠️ DB query error: {str(e)[:100]}")
        return None if fetch_one else []


# === НИЗКОУРОВНЕВЫЕ ФУНКЦИИ С КЭШИРОВАНИЕМ ===
def get_client_id_by_employee_id(employee_id):
    """Получает client_id по employee_id"""
    if not employee_id:
        return None
    key = f"client_by_employee_{employee_id}"
    result = cached_db_query(key, """SELECT client_id FROM client_users WHERE id = %s LIMIT 1""", (employee_id,), fetch_one=True)
    return result[0] if result else None


def get_employee_id_by_uuid(employee_uuid):
    """Получает employee_id по UUID"""
    if not is_valid_uuid(employee_uuid):
        return None
    key = f"employee_id_by_uuid_{employee_uuid}"
    result = cached_db_query(key, "SELECT id FROM users WHERE uuid = %s", (employee_uuid,), fetch_one=True)
    return int(result[0]) if result and result[0] is not None else None


def get_employee_uuid_by_phone(phone):
    """Получает UUID по телефону"""
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    key = f"uuid_by_phone_{normalized_phone}"
    result = cached_db_query(key, "SELECT uuid FROM users WHERE phone = %s", (normalized_phone,), fetch_one=True)
    return result[0] if result else None


def get_employee_uuid_by_id(employee_id):
    """Получает UUID по employee_id"""
    # Обработка float значений
    if pd.isna(employee_id) or not str(employee_id).strip():
        return None
    try:
        employee_id = int(float(employee_id))
        employee_id_str = str(employee_id).strip()
        if '.' in employee_id_str:
            employee_id_str = employee_id_str.split('.')[0]  # Удаляем дробную часть без округления
        employee_id = int(employee_id_str)
    except (ValueError, TypeError):
        return None
    key = f"uuid_by_id_{employee_id}"
    result = cached_db_query(key, "SELECT uuid FROM users WHERE id = %s", (employee_id,), fetch_one=True)
    return result[0] if result else None


def get_category_id_by_position(position_id):
    """Получает category_id по position_id"""
    if not position_id:
        return None
    key = f"category_by_position_{position_id}"
    result = cached_db_query(key, "SELECT category_id FROM positions WHERE id = %s LIMIT 1", (position_id,),
                             fetch_one=True)
    return result[0] if result else None


def get_client_id_by_position(position_id):
    """Получает client_id по position_id"""
    if not position_id:
        return None
    key = f"client_by_position_{position_id}"
    result = cached_db_query(key, "SELECT client_id FROM positions WHERE id = %s LIMIT 1", (position_id,),
                             fetch_one=True)
    return result[0] if result else None


def get_brand_id_by_client_id(client_id):
    """Получает brand_id по client_id (если один бренд)"""
    if client_id is None or pd.isna(client_id):
        return None
    try:
        client_id = int(client_id)
    except (ValueError, TypeError):
        return None
    key = f"brand_by_client_{client_id}"
    results = cached_db_query(key, "SELECT id FROM brands WHERE client_id = %s", (client_id,))
    return results[0][0] if results and len(results) == 1 else None


def get_client_id_by_brand_id(brand_id):
    """Получает client_id по brand_id"""
    if not brand_id:
        return None
    key = f"client_by_brand_{brand_id}"
    result = cached_db_query(key, "SELECT client_id FROM brands WHERE id = %s", (brand_id,), fetch_one=True)
    return result[0] if result else None


# === БИЗНЕС-ЛОГИКА И ВАЛИДАЦИЯ ===
def validate_coordinates(lat, lon):
    """Валидация географических координат"""
    if lat is None and lon is None:
        return True  # Пропускаем если обе координаты не указаны

    lat_val = safe_float(lat) if lat is not None else None
    lon_val = safe_float(lon) if lon is not None else None

    if lat_val is None and lon_val is None:
        return True

    if lat_val is None or lon_val is None:
        return False

    return -90 <= lat_val <= 90 and -180 <= lon_val <= 180


def validate_required_fields(row):
    """Проверяет обязательные поля"""
    required_fields = ['name', 'address', 'employee_id']
    missing_fields = [
        field for field in required_fields
        if field not in row or not is_valid_value(row[field])
    ]
    if missing_fields:
        project_name = row.get('name', 'Unknown')
        return f"⚠️ Project: {project_name}, Error: missing required fields {', '.join(missing_fields)}"
    return None


def get_employee_data(row):
    """Обрабатывает данные о сотруднике (бизнес-логика)"""
    employee_identifier = row.get('employee_id', '')
    project_name = row.get('name', 'Unknown')

    # Нормализация идентификатора
    if pd.notna(employee_identifier):
        if isinstance(employee_identifier, (int, float)):
            employee_identifier = str(int(employee_identifier)).strip()
        else:
            employee_identifier = str(employee_identifier).strip()
    else:
        employee_identifier = ''

    # Стратегии обработки в зависимости от типа идентификатора
    handlers = {
        'phone': lambda: (get_employee_uuid_by_phone(employee_identifier),get_employee_id_by_uuid(get_employee_uuid_by_phone(employee_identifier))
                          if get_employee_uuid_by_phone(employee_identifier) else None),
        'id': lambda: (get_employee_uuid_by_id(int(float(employee_identifier))) if employee_identifier and not pd.isna(employee_identifier) else None,
                       int(float(employee_identifier)) if employee_identifier and not pd.isna(employee_identifier) else None),
        'uuid': lambda: (employee_identifier if is_valid_uuid(employee_identifier) else None, get_employee_id_by_uuid(employee_identifier)
                         if is_valid_uuid(employee_identifier) else None)
    }

    # Проверка валидности режима обработки
    if process_by not in handlers:
        return None, None, f"⚠️ Project: {project_name}, Error: invalid process_by mode '{process_by}'"

    # Получение данных сотрудника
    try:
        employee_uuid, employee_id = handlers[process_by]()
    except (ValueError, TypeError):
        return None, None, f"⚠️ Project: {project_name}, Error: invalid ID format '{employee_identifier}'"

    # Проверка корректности полученных данных
    if not employee_uuid:
        return None, None, f"⚠️ Project: {project_name}, Error: employee UUID not found for {employee_identifier}"
    if employee_id is None:
        return None, None, f"⚠️ Project: {project_name}, Error: employee ID not found for {employee_identifier}"

    return employee_uuid, employee_id, None


def get_client_data(row, employee_id, position_client_id=None):
    """Обрабатывает данные о клиенте с проверкой соответствия (бизнес-логика)"""
    project_name = row.get('name', 'Unknown')
    if employee_id is None:
        return None, None, f"⚠️ Project: {project_name}, Error: employee_id is None"

    excel_client_id = get_valid_int(row.get('client_id'))
    brand_id = get_valid_int(row.get('brand_id'))
    employee_client_id = get_client_id_by_employee_id(employee_id)

    # Стратегия определения client_id (приоритеты)
    client_id = None
    if excel_client_id is not None:
        client_id = excel_client_id
    elif position_client_id is not None:
        client_id = position_client_id
    elif brand_id is not None:
        # Ищем client_id по brand_id
        client_id = get_client_id_by_brand_id(brand_id)

    # FALLBACK: берём client_id из сотрудника
    if client_id is None and employee_client_id is not None:
        client_id = employee_client_id
        print(f"ℹ️ Project: {project_name}, Using employee's client_id={client_id} as fallback")

    # Проверка соответствия client_id для сотрудника
    if client_id is not None and employee_client_id is not None and employee_client_id != client_id:
        return None, brand_id, f"⚠️ Project: {project_name}, Error: employee client_id ({employee_client_id}) does not match project client_id ({client_id})"

    # Проверка соответствия brand_id и client_id
    if client_id is not None and brand_id is not None:
        brand_client_id = get_client_id_by_brand_id(brand_id)
        if brand_client_id is not None and brand_client_id != client_id:
            return None, brand_id, f"⚠️ Project: {project_name}, Error: brand_id {brand_id} client_id ({brand_client_id}) does not match project client_id ({client_id})"

    return client_id, brand_id, None


def get_position_data(row, client_id_from_row, employee_id=None):
    """Обрабатывает данные о позиции с проверкой уникальности связки (бизнес-логика)"""
    project_name = row.get('name', 'Unknown')
    category_id = get_valid_int(row.get('category_id'))
    position_id = get_valid_int(row.get('position_id'))
    excel_client_id = get_valid_int(row.get('client_id'))
    excel_category_id = get_valid_int(row.get('category_id'))

    # Получение category_id из БД по position_id
    if category_id is None and position_id:
        category_id = get_category_id_by_position(position_id)

    # Проверка наличия category_id
    if category_id is None:
        return None, None, None, f"⚠️ Project: {project_name}, Error: category_id not found"

    # Поиск позиции по ID или по связке (client_id + category_id)
    if position_id is not None:
        # Проверка корректности указанной позиции
        db_client_id = get_client_id_by_position(position_id)
        db_category_id = get_category_id_by_position(position_id)

        if db_client_id is None or db_category_id is None:
            return None, None, None, f"⚠️ Project: {project_name}, Error: position_id {position_id} not found in database"

        # КРИТИЧЕСКАЯ ПРОВЕРКА: соответствие клиента
        if client_id_from_row is not None and db_client_id != client_id_from_row:
            return None, None, None, f"⚠️ Project: {project_name}, Error: position_id {position_id} does not belong to client_id {client_id_from_row}"

        # КРИТИЧЕСКАЯ ПРОВЕРКА: соответствие категории
        if category_id is not None and db_category_id != category_id:
            return None, None, None, f"⚠️ Project: {project_name}, Error: position_id {position_id} category_id {db_category_id} does not match category_id {category_id}"

        # КРИТИЧЕСКАЯ ПРОВЕРКА: соответствие Excel-данным
        if excel_client_id is not None and db_client_id != excel_client_id:
            return None, None, None, f"⚠️ Project: {project_name}, Error: client_id {excel_client_id} does not match position_id {position_id}"
        if excel_category_id is not None and db_category_id != excel_category_id:
            return None, None, None, f"⚠️ Project: {project_name}, Error: category_id {excel_category_id} does not match position_id {position_id}"

        return position_id, category_id, db_client_id, None
    else:
        # Поиск позиции по связке client_id + category_id
        search_client_id = client_id_from_row

        # Если client_id не указан, пробуем получить из brand_id
        if search_client_id is None:
            brand_id = get_valid_int(row.get('brand_id'))
            if brand_id:
                search_client_id = get_client_id_by_brand_id(brand_id)

        # используем client_id сотрудника как последний fallback
        if search_client_id is None and employee_id is not None:
            search_client_id = get_client_id_by_employee_id(employee_id)
            if search_client_id is not None:
                print(f"ℹ️ Project: {project_name}, Using employee's client_id={search_client_id} for position search")

        if search_client_id is None:
            return None, None, None, f"⚠️ Project: {project_name}, Error: cannot determine client_id to find position"

        # Использование потокобезопасного кэша
        if not hasattr(_cache, 'data'):
            _cache.data = {}

        # Ищем позиции по связке client_id + category_id
        key = f"positions_{search_client_id}_{category_id}"
        if key not in _cache.data:
            _cache.data[key] = execute_db_query(
                "SELECT id FROM positions WHERE client_id = %s AND category_id = %s",
                (search_client_id, category_id)
            )
        positions = _cache.data[key]

        # Проверка количества позиций
        if not positions:
            return None, None, None, f"⚠️ Project: {project_name}, Error: no positions found for client_id = {search_client_id} and category_id: {category_id}"

        if len(positions) > 1:
            position_ids = ", ".join(str(p[0]) for p in positions)
            return None, None, None, f"⚠️ Project: {project_name}, Error: MULTIPLE positions ({len(positions)}) found for client_id {search_client_id} + category_id {category_id}. IDs: {position_ids}"

        # Успешное нахождение единственной подходящей позиции
        position_id = positions[0][0]
        db_client_id = search_client_id

        # Дополнительная проверка соответствия
        db_category_id = get_category_id_by_position(position_id)
        if category_id is not None and db_category_id != category_id:
            return None, None, None, f"⚠️ Project: {project_name}, Error: found position category_id {db_category_id} does not match required {category_id}"

        return position_id, category_id, db_client_id, None


def get_brand_data(row, client_id, brand_id):
    """Получает данные бренда: обработка и валидация"""
    project_name = row.get('name', 'Unknown')

    # Если brand_id указан - проверяем принадлежность клиенту
    if brand_id is not None:
        brand_client_id = get_client_id_by_brand_id(brand_id)
        if brand_client_id is None:
            return None, f"⚠️ Project: {project_name}, Error: brand_id {brand_id} does not exist"
        return brand_id, None

    # Если brand_id не указан - ищем единственный бренд клиента
    if client_id is None:
        return None, f"⚠️ Project: {project_name}, Error: cannot determine brand - client_id is None"

    brand_id = get_brand_id_by_client_id(client_id)
    if brand_id is None:
        return None, f"⚠️ Project: {project_name}, Error: no single brand found for client_id={client_id}"

    return brand_id, None


# === ФОРМИРОВАНИЕ PAYLOAD ===
def create_payload(row, position_id, category_id, brand_id):
    """Формирует payload для создания проекта"""
    # Улучшенная обработка gender
    genders = {
        'MALE': {'м', 'муж', 'm', 'man', 'male', '0'},
        'FEMALE': {'ж', 'жен', 'w', 'woman', 'women', 'f', 'female', '1'},
        'NONE': {'все', 'нет', 'all', 'none', '2', ''}
    }
    gender_value = str(row.get('gender', '')).strip().lower() if is_valid_value(row.get('gender')) else ''
    gender = next((g for g, vals in genders.items() if gender_value in vals), 'NONE')

    # Валидация координат
    lat = row.get('latitude')
    lon = row.get('longitude')
    if (is_valid_value(lat) or is_valid_value(lon)) and not validate_coordinates(lat, lon):
        raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")

    # Формирование данных для запроса
    return {
        "name": str(row.get('name', '')).strip(),
        "position": {
            "id": position_id,
            "category": {"id": category_id}
        },
        "address": str(row.get('address', '')).strip(),
        "preScreening": prescreening,
        "projectShiftConfigs": [
            {"startShift": start_shift, "projectShiftConfig": start_photo, "name": start_name},
            {"endShift": end_shift, "projectShiftConfig": end_photo, "name": end_name}
        ],
        "latitude": safe_float(row.get('latitude')) if is_valid_value(row.get('latitude')) else None,
        "longitude": safe_float(row.get('longitude')) if is_valid_value(row.get('longitude')) else None,
        "idRequirementDocuments": required_documents or [],
        "person": {
            "gender": gender,
            # "gender": "NONE" if not is_valid_value(row.get('gender')) else str(row.get('gender', '')).strip() or "NONE",
            "minAge": get_valid_int(row.get('min_age', 0)) or 0,
            "maxAge": get_valid_int(row.get('max_age', 0)) or 0
        },
        "numberShop": "-" if not is_valid_value(row.get('number_shop')) else str(
            row.get('number_shop', '')).strip() or "-",
        "brand": {"id": brand_id},
        "descriptionWizard": {
            "steps": [
                {"position": 0, "type": "Что делать?", "text": "Описание задания"},
                {"position": 1, "type": "Как выйти на задание?", "text": "Записаться в приложении"}
            ]
        }
    }


# === РАБОТА С API И ОБРАБОТКА ОШИБОК ===
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


def handle_api_response(response: requests.Response, project_name: str) -> tuple[bool, str | None, ApiErrorType | None]:
    """Унифицированная обработка HTTP-ответов. Возвращает: (успешно, сообщение, тип_ошибки)"""
    status = response.status_code

    # Критические ошибки авторизации
    if status in (401, 403):
        ABORT_FLAG.set()
        return False, f"❌ FATAL: Auth error {status} for '{project_name}'. Stopping all operations.", ApiErrorType.AUTH

    # Серверные ошибки (5xx)
    if status >= 500:
        try:
            error_detail = response.json().get("message", "")[:100]
        except Exception:
            error_detail = response.text[:100] or "No error details"
        return False, f"🔥 Server error {status}: {error_detail}", ApiErrorType.SERVER

    # Успешные статусы и клиентские ошибки (включая 400) обрабатываются в основном цикле
    return True, None, None


def format_response(row, response):
    """Форматирует ответ от API для логирования"""
    name = row.get('name', 'Unknown')
    try:
        status = response.status_code
        response_data = response.json()
        if 200 <= status < 300:
            maps = response_data.get('maps', {})
            return f"✅ Project: {name} (ID: {maps.get('id', 'N/A')}, TZ: {maps.get('tz', 'N/A')}, UUID: {maps.get('uuidCode', 'N/A')})"
        # Для ошибок (включая 400)
        message = response_data.get('message', str(response_data))[:200]
        return f"❌ Project: {name}, Status: {status}, Message: {message}"
    except Exception as e:
        return f"⚠️ Project: {name}, Parse error: {str(e)[:50]}"


def safe_request(func, *args, max_retries=2, **kwargs):
    """Единая точка для ретраев сетевых запросов и 5xx ошибок"""
    for attempt in range(max_retries + 1):
        try:
            response = func(*args, **kwargs)
            # Повторные попытки для 5xx ошибок
            if response.status_code >= 500 and attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt == max_retries:
                raise
            time.sleep(1 * (attempt + 1))
    return None


def log_messages(messages, log_file):
    """Записывает сообщения в лог-файл"""
    if not (enable_log and messages):
        return
    # Повторные попытки при ошибке записи в лог
    for attempt in range(3):
        try:
            with _log_lock, open(log_file, 'a', encoding='utf-8') as log:
                log.write('\n'.join(messages) + '\n')
            return
        except Exception as e:
            if attempt == 2:
                print(f"⚠️ FAILED to write to log after 3 attempts: {e}")
            time.sleep(0.5)


# === ОСНОВНОЙ КОД ===
start_time = datetime.now()
auth = load_auth()

# Критические проверки перед запуском
check_db_connection()  # Проверка подключения к БД
validate_api_connection(auth, host)  # Проверка API и валидности токена

# Чтение и валидация данных
required_columns = {'name', 'address', 'employee_id', 'client_id', 'brand_id',
                    'category_id', 'position_id', 'gender', 'max_age', 'min_age',
                    'number_shop', 'latitude', 'longitude'}

try: # Читаем только первый лист и нужные колонки
    df = pd.read_excel(input_file, sheet_name=0, usecols=lambda x: str(x).strip() in required_columns)
except Exception as e:
    sys.exit(f"❌ Failed to read Excel file: {str(e)}")

# Проверка обязательных колонок
missing_columns = required_columns - set(str(col).strip() for col in df.columns)
if missing_columns:
    sys.exit(f"❌ Missing required columns: {', '.join(missing_columns)}")

if len(df) > 5000: print(f"⚠️ Warning: Excel file contains {len(df)} rows. Consider splitting the file.")

total = len(df)
if total == 0:
    print("⚠️ No valid projects found in Excel file after filtering empty rows. Nothing to process.")
    sys.exit(0)

if enable_log:
    with open(log_file, 'w', encoding='utf-8') as log:
        log.write(f'# {script_name}, {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')


# === МНОГОПОТОЧНАЯ ОБРАБОТКА ===
def process_project(row, auth, host):
    """Основная функция обработки проекта с унифицированной обработкой ошибок"""
    project_name = row.get('name', 'Unknown')

    # Проверка глобального флага остановки
    if ABORT_FLAG.is_set():
        return None, f"🛑 Skipped '{project_name}': global abort triggered", ApiErrorType.AUTH

    try:
        # ШАГ 1: Валидация обязательных полей
        error = validate_required_fields(row)
        if error:
            return None, error, ApiErrorType.CLIENT

        # ШАГ 2: Получение данных сотрудника
        employee_uuid, employee_id, error = get_employee_data(row)
        if error:
            return None, error, ApiErrorType.CLIENT

        # ШАГ 3: Получение данных позиции
        position_id, category_id, position_client_id, error = get_position_data(
            row,
            client_id_from_row=None,
            employee_id=employee_id
        )
        if error:
            return None, error, ApiErrorType.CLIENT

        # ШАГ 4: Получение данных клиента (уже с position_client_id)
        client_id, brand_id, error = get_client_data(row, employee_id, position_client_id)
        if error:
            return None, error, ApiErrorType.CLIENT

        # ШАГ 5: Проверка бренда
        brand_id, error = get_brand_data(row, client_id, brand_id)
        if error:
            return None, error, ApiErrorType.CLIENT

        # ШАГ 6: Формирование payload
        try:
            payload = create_payload(row, position_id, category_id, brand_id)
        except ValueError as e:
            return None, f"⚠️ Project: {project_name}, Error: {str(e)}", ApiErrorType.CLIENT

        # ШАГ 7: Отправка запроса с ретраями
        response = safe_request(
            requests.post,
            url=f"https://{host}/v2/mobile/projects/",
            json=payload,
            headers={
                "accept": "*/*",
                "uuid": employee_uuid,
                "Authorization": auth,
                "Content-Type": "application/json"
            },
            timeout=30
        )

        # ШАГ 8: Обработка ответа
        success, msg, error_type = handle_api_response(response, project_name)
        if not success:
            if error_type == ApiErrorType.AUTH:
                ABORT_FLAG.set()
            return None, msg, error_type

        # Возврат результата
        return response, project_name, None

    except Exception as e:
        return None, f"💥 Unexpected error for '{project_name}': {str(e)}", ApiErrorType.CLIENT
    finally:
        # Гарантированное закрытие соединения с БД для текущего потока
        close_db_connection()

# === ЗАПУСК ОБРАБОТКИ ===
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(process_project, row, auth, host): idx for idx, (_, row) in enumerate(df.iterrows())}
    success_count = error_count = 0
    completed = 0

    for future in as_completed(futures):
        idx = futures[future]
        row = df.iloc[idx]
        project_name = row.get('name', 'Unknown')
        completed += 1

        # Глобальная остановка при критических ошибках
        if ABORT_FLAG.is_set():
            for f in futures:
                f.cancel()
            print("\n🛑 GLOBAL ABORT TRIGGERED. Stopping all pending operations.")
            break

        try:
            result = future.result(timeout=90)
            # Проверка формата результата
            if not result or len(result) < 3:
                error_count += 1
                status_msg = f"⚠️ Project: {project_name}, Error: invalid result format"
                progress_msg = f"Сделано {completed} из {total}."
                print(f"{status_msg}\n{progress_msg}")
                if enable_log:
                    log_messages([status_msg, progress_msg], log_file)
                continue

            response, project_name, error_type = result

            # Обработка результата
            if response is None:
                error_count += 1
                status_msg = project_name  # Сообщение об ошибке
            else:
                # Форматируем ответ (успех или ошибка 400)
                status_msg = format_response(row, response)
                if 200 <= response.status_code < 300:
                    success_count += 1
                else:
                    error_count += 1
        except Exception as e:
            error_count += 1
            status_msg = f"⚠️ Thread crashed for project '{project_name}': {str(e)}"

        # Отображение прогресса
        progress_msg = f"Сделано {completed} из {total}."
        print(f"{status_msg}\n{progress_msg}")

        # Логирование
        if enable_log:
            log_messages([status_msg, progress_msg], log_file)

        # Проверка после каждой итерации
        if ABORT_FLAG.is_set():
            break

# === ЗАКРЫТИЕ РЕСУРСОВ ===
try:
    # Статистика
    duration = (datetime.now() - start_time).total_seconds()
    stats = [
        f"\n✅ Completed: {success_count}/{total}",
        f"❌ Failed: {error_count}/{total}",
        f"⏱️ Time: {duration:.2f} seconds",
        f"⚡️ Speed: {total / max(duration, 0.1):.2f} projects/sec" if duration > 0 else "⚡️ Speed: N/A",
    ]

    # Прогресс бар
    progress = int((success_count / total) * 30) if total > 0 else 0
    bar = "█" * progress + "░" * (30 - progress)
    progress_bar_str = f"📈 Progress: [{bar}] {success_count}/{total} ({success_count / total * 100:.1f}%)"

    print('\n'.join(stats))
    print(progress_bar_str)

    # Запись статистики в лог
    if enable_log:
        log_messages(stats + [progress_bar_str], log_file)

finally:
    # Закрытие соединений с БД для всех потоков
    close_db_connection()