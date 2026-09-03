import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

# === ЖЕСТКИЕ ПАРАМЕТРЫ (ПОД НАСТРОЙКУ) ===
MAX_WORKERS = 3  # Мало потоков чтобы не блокировали сервер
CMD_TIMEOUT = 45  # Таймаут на команду в секундах
BASH_PATH = r"C:\Program Files\Git\bin\bash.exe"  # Путь к Git Bash

# === ПРОВЕРКА BASH ===
if not os.path.exists(BASH_PATH):
    sys.exit(f"❌ Git Bash не найден: {BASH_PATH}. Укажите правильный путь.")


# === ЧТЕНИЕ И ОЧИСТКА КОМАНД ===
def clean_command(line):
    """Удаляет мусор после табуляции и лишние пробелы"""
    return line.split('\t')[0].split('|')[0].strip().replace('  "', '"')


cmds = []
with open('D:/WORK/python/bash.sh', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            cleaned = clean_command(line)
            if cleaned.startswith('curl'):
                cmds.append(cleaned)

total = len(cmds)
if total == 0:
    sys.exit("❌ Нет валидных команд для выполнения")

print(f"🚀 Запускаем {total} команд в {MAX_WORKERS} потоках (таймаут: {CMD_TIMEOUT} сек)...")


# === БЕЗОПАСНОЕ ВЫПОЛНЕНИЕ КОМАНДЫ ===
def safe_run(cmd):
    """Выполняет команду с таймаутом и логированием"""
    try:
        result = subprocess.run(
            [BASH_PATH, '-c', cmd],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=CMD_TIMEOUT
        )
        return result, None
    except TimeoutError:
        return None, "ТАЙМАУТ"
    except Exception as e:
        return None, str(e)


# === МНОГОПОТОЧНАЯ ОБРАБОТКА ===
completed = 0
errors = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(safe_run, cmd): cmd for cmd in cmds}

    for future in as_completed(futures):
        cmd = futures[future]
        try:
            result, error = future.result()
        except Exception as e:
            result, error = None, f"ПОТОК_АВАРИЯ: {str(e)}"

        completed += 1

        if error:
            errors += 1
            print(f"\n{completed}/{total} ✗ [ТАЙМАУТ/{error}]")
            print(f"   $ {cmd[:100]}...")
        elif result.returncode == 0:
            print(f"{completed}/{total} ✓")
        else:
            errors += 1
            # Берем только первые 200 символов ошибки для читаемости
            stderr = result.stderr.strip()[:200] or result.stdout.strip()[:200]
            print(f"\n{completed}/{total} ✗ [Код: {result.returncode}]")
            print(f"   $ {cmd[:100]}...")
            print(f"   💥 {stderr}")

print(f"\n✅ ГОТОВО: {completed - errors}/{total} успешных")
if errors:
    print(f"❌ ОШИБОК: {errors}/{total}. Проверьте логи выше")