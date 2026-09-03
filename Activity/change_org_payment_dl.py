import sys
import os
import time
import logging
import psycopg2
from psycopg2 import sql, Error
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from decimal import Decimal, getcontext
# ДЛЯ ВКЛЮЧЕНИЯ КРЕДОВ ИЗ ENV ФАЙЛА ВКЛЮЧИТЬ ЭТО, db_config = get_db_config() И ЗАКОММЕНТИРОВАТЬ БЛОК db_config{}
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent));from db_config import get_db_config

# КОРРЕКТИРОВКА ОРГАНИЗАЦИИ-ПЛАТЕЛЬЩИКА И БАЛАНСОВ ПО АКТИВНОСТЯМ И ИХ ТРАНЗАКЦИЯМ

# === КОНФИГ ===
to_org = 60912038             # за чей счет, целевая организация по умолчанию
paid_by_client = False         # True False (True = платит владелец активности, False = платит to_org)
enable_logging = True         # True False
getcontext().prec = 28        # точность, не трогать (нужно для предотвращения ошибок округления)
db_config = get_db_config()   # Динамическая загрузка из .ENV
input_file = 'D:/WORK/python/list_activities.txt'

# === ЛОГИРОВАНИЕ ===
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if enable_logging:
    log_file = os.path.join(os.path.dirname(__file__), 'change_org_payment.log')
    # Файловый обработчик с временной меткой
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)

# Консольный обработчик без временной метки
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)


# === ФУНКЦИИ ===
def get_activity_owner_org(activity_id: int) -> int:
    """Возвращает ID организации-владельца активности через связь с вакансией"""
    with psycopg2.connect(**db_config, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT client_id 
                FROM vacancies v
                JOIN executor_work_activity ewa ON v.id = ewa.vacancy_id 
                WHERE ewa.id = %s
            """, (activity_id,))
            if result := cur.fetchone():
                return result[0]
            raise ValueError(f"Не найден владелец для активности {activity_id}")


def retry_on_db_errors(func, max_retries=3, delay=2):
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_exception = e
                wait_time = delay * (2 ** attempt)
                logging.warning(f"Попытка {attempt + 1}/{max_retries} не удалась. Ожидание {wait_time:.1f} сек...")
                time.sleep(wait_time)

        # Гарантируем обработку всех путей
        raise last_exception or RuntimeError("Все попытки исчерпаны без сохранения исключения")
    return wrapper


@retry_on_db_errors
def process_activity(aid: str) -> Tuple[str, bool, Optional[str], Optional[Dict[str, Any]]]:
    try:
        clean_id = ''.join(char for char in aid if char.isdigit())
        if not clean_id: raise ValueError(f"Некорректный ID: {aid}")
        activity_id = int(clean_id)

        with psycopg2.connect(**db_config, connect_timeout=10, options='-c statement_timeout=30000') as conn:
            with conn.cursor() as cur:
                # Валидация активности
                cur.execute("SELECT 1 FROM executor_work_activity WHERE id = %s", (activity_id,))
                if not cur.fetchone(): raise ValueError(f"Активность {activity_id} не существует")

                # Расширенная логика модификации транзакций в зависимости от режима оплаты
                target_org = to_org
                exclusion_org = to_org
                employee_id = None

                if paid_by_client:
                    owner_org = get_activity_owner_org(activity_id)
                    target_org = owner_org
                    exclusion_org = owner_org
                    # Получение employee_id для активности
                    cur.execute("""
                        SELECT v.employee_id 
                        FROM vacancies v
                        JOIN executor_work_activity ewa ON v.id = ewa.vacancy_id 
                        WHERE ewa.id = %s
                    """, (activity_id,))
                    emp_row = cur.fetchone()
                    if not emp_row: raise ValueError(f"Не найден employee_id для активности {activity_id}")
                    employee_id = emp_row[0]

                # Динамический выбор entity_type в зависимости от режима
                entity_type_filter = 'Organization' if paid_by_client else 'Employee'

                # Получение транзакции с ID для модификации
                cur.execute(sql.SQL("""
                    SELECT id, amount, decimal_amount, organization_id, entity_id 
                    FROM payment_transaction 
                    WHERE executor_work_activity_id = %s 
                    AND entity_type = %s 
                    AND status = 'APPROVED'
                    AND type = 'INTERNAL'
                    ORDER BY created_at LIMIT 1
                """), (activity_id, entity_type_filter))

                if not (row := cur.fetchone()): return clean_id, False, "Нет подходящих транзакций", None

                trans_id, amount, decimal_amount, src_org, entity_id = row

                # === ИСПРАВЛЕНО: Универсальная проверка блокировки транзакций ===
                block_id = to_org if not paid_by_client else owner_org
                if src_org == block_id or entity_id == block_id:
                    mode = "Ventra" if not paid_by_client else "Client"
                    return clean_id, False, f"Транзакция заблокирована: {block_id} в режиме {mode}", None
                int_amount = abs(int(Decimal(str(amount or 0)).to_integral_value()))
                use_decimal = decimal_amount is not None
                dec_amount = abs(Decimal(str(decimal_amount))) if use_decimal else None
                if paid_by_client: src_org = to_org

                # Обновление entity_type и entity_id ТОЛЬКО для выбранной транзакции И organization_id для ВСЕХ транзакций
                cur.execute(sql.SQL("""
                    UPDATE payment_transaction SET organization_id = %s 
                    WHERE executor_work_activity_id = %s 
                    AND status = 'APPROVED' 
                    AND type = ANY(%s)
                """), (target_org, activity_id, ['INTERNAL', 'EXTERNAL']))

                # Обновление entity_type и entity_id ТОЛЬКО для найденной транзакции
                if paid_by_client:
                    cur.execute("""
                        UPDATE payment_transaction 
                        SET entity_id = %s, entity_type = 'Employee'
                        WHERE id = %s
                    """, (employee_id, trans_id))
                else:
                    cur.execute("""
                        UPDATE payment_transaction 
                        SET entity_id = %s, entity_type = 'Organization'
                        WHERE id = %s
                    """, (target_org, trans_id))

                # Обновление режима компенсации в активности (COMPENSATION_CLIENT или COMPENSATION_VENTRA)
                compensation_mode = 'COMPENSATION_CLIENT' if paid_by_client else 'COMPENSATION_VENTRA'
                cur.execute("""
                    UPDATE executor_work_activity 
                    SET compensation = %s 
                    WHERE id = %s
                """, (compensation_mode, activity_id))

                # Получение балансов с блокировкой
                cur.execute("""
                    SELECT id, COALESCE(balance, 0), COALESCE(decimal_balance, 0) 
                    FROM organization 
                    WHERE id IN (%s, %s) FOR UPDATE
                """, (target_org, src_org))

                orgs = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
                if target_org not in orgs or src_org not in orgs: raise ValueError("Организации не найдены")

                bal_target, dec_target = orgs[target_org]
                bal_src, dec_src = orgs[src_org]

                # Обновление основных балансов
                cur.execute("""
                    UPDATE organization SET balance = balance - %s WHERE id = %s;
                    UPDATE organization SET balance = balance + %s WHERE id = %s;
                """, (int_amount, target_org, int_amount, src_org))

                # Обновление decimal балансов с обработкой NULL
                if use_decimal:
                    cur.execute("""
                        UPDATE organization SET decimal_balance = COALESCE(decimal_balance, 0) - %s WHERE id = %s;
                        UPDATE organization SET decimal_balance = COALESCE(decimal_balance, 0) + %s WHERE id = %s;
                    """, (dec_amount, target_org, dec_amount, src_org))

                # Получение новых балансов
                cur.execute("SELECT COALESCE(balance, 0), COALESCE(decimal_balance, 0) FROM organization WHERE id = %s", (target_org,))
                new_target = cur.fetchone()
                cur.execute("SELECT COALESCE(balance, 0), COALESCE(decimal_balance, 0) FROM organization WHERE id = %s", (src_org,))
                new_src = cur.fetchone()

                return (clean_id, True, None, {
                    'activity_id': clean_id,
                    'amount': int_amount,
                    'decimal_amount': float(dec_amount) if use_decimal else None,
                    'use_decimal': use_decimal,
                    'to_org': target_org,
                    'src_org': src_org,
                    'bal_to_before': int(bal_target),
                    'bal_to_after': int(new_target[0]),
                    'dec_to_before': float(dec_target),
                    'dec_to_after': float(new_target[1]) if use_decimal else None,
                    'bal_src_before': int(bal_src),
                    'bal_src_after': int(new_src[0]),
                    'dec_src_before': float(dec_src),
                    'dec_src_after': float(new_src[1]) if use_decimal else None
                })
    except (ValueError, Error, Exception) as e:
        err_type = "Валидация" if isinstance(e, ValueError) else "DB error" if isinstance(e, Error) else "Системная ошибка"
        err_msg = str(e).splitlines()[0]
        if isinstance(e, Error): err_msg = f"{err_type} {e.pgcode}: {err_msg}"
        logging.error(f"{err_type} {aid}: {err_msg}", exc_info=enable_logging)
        return aid, False, f"{err_type}: {err_msg}", None

# === ОСНОВНОЙ ПРОЦЕССИНГ ===
def main() -> None:
    start = datetime.now()
    ok = 0

    with open(input_file) as f:
        activities = [l.strip() for l in f if l.strip()]

    total = len(activities)
    if not total:
        logging.error("❌ Нет активностей для обработки")
        return

    for i, aid in enumerate(activities, 1):
        cleaned_aid, success, error, result = process_activity(aid)
        if success and result:
            ok += 1
            # Форматирование вывода
            decimal_display = f"{result['decimal_amount']:.2f}" if result['use_decimal'] else "N/A"
            lines = [
                f"✅ SUCCESS: {result['activity_id']} (amount: {result['amount']}, decimal_amount: {decimal_display})",
                f"Org: {result['to_org']}, balance: {result['bal_to_before']} - {result['amount']} = {result['bal_to_after']}" +
                (f", decimal: {result['dec_to_before']:.2f} - {result['decimal_amount']:.2f} = {result['dec_to_after']:.2f}" if result['use_decimal'] else ", decimal: skipped"),
                f"Org: {result['src_org']}, balance: {result['bal_src_before']} + {result['amount']} = {result['bal_src_after']}" +
                (f", decimal: {result['dec_src_before']:.2f} + {result['decimal_amount']:.2f} = {result['dec_src_after']:.2f}" if result['use_decimal'] else ", decimal: skipped")
            ]
            logging.info("\n".join(lines))
        else:
            logging.error(f"❌ ОШИБКА: {cleaned_aid} - {error}")
        logging.info(f"Сделано {i} из {total}\n")

    duration = (datetime.now() - start).total_seconds()
    progress = int((ok / total) * 30) if total > 0 else 0
    logging.info(
        f"✅ Успешно: {ok}/{total}\n❌ Ошибок: {total - ok}\n"
        f"⏱️ Время: {duration:.2f} сек\n⚡ Скорость: {total/duration:.2f} актив/сек\n"
        f"📊 Эффективность: {ok/total*100:.1f}%\n"
        f"📈 Прогресс: [{'█'*progress}{'░'*(30-progress)}] {ok}/{total} ({ok/total*100:.1f}%)\n"
    )

if __name__ == "__main__":
    main()