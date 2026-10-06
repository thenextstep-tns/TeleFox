import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
data_dir_env = os.environ.get("TELEFOX_DATA_DIR")
if data_dir_env:
    BASE_DIR = Path(data_dir_env)
else:
    BASE_DIR = Path(__file__).resolve().parent

ENV_PATH = BASE_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Каталог для хранения файлов сессий
SESSIONS_DIR = BASE_DIR / "sessions"
try:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Файл с описанием аккаунтов
ACCOUNTS_FILE = BASE_DIR / "accounts.json"

def reload_config(new_base_dir: str):
    global BASE_DIR, ENV_PATH, SESSIONS_DIR, ACCOUNTS_FILE
    global TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_2FA_PASSWORD, N8N_WEBHOOK_URL
    global MONGODB_URI, MONGODB_DB_NAME, DUPLICATE_DOCS_TO_DB
    BASE_DIR = Path(new_base_dir)
    ENV_PATH = BASE_DIR / ".env"
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    SESSIONS_DIR = BASE_DIR / "sessions"
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    ACCOUNTS_FILE = BASE_DIR / "accounts.json"
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
    TELEGRAM_2FA_PASSWORD = os.getenv("TELEGRAM_2FA_PASSWORD", "")
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/telegram-doc")
    MONGODB_URI = os.getenv("MONGODB_URI", "")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "teamo")
    DUPLICATE_DOCS_TO_DB = os.getenv("DUPLICATE_DOCS_TO_DB", "true").lower() in ("true", "1", "yes")

# Глобальные параметры
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_2FA_PASSWORD = os.getenv("TELEGRAM_2FA_PASSWORD", "")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/telegram-doc")

# Параметры MongoDB Atlas
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "teamo")
DUPLICATE_DOCS_TO_DB = os.getenv("DUPLICATE_DOCS_TO_DB", "true").lower() in ("true", "1", "yes")

# Параметры следующих этапов (заглушки)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN", "")
AMOCRM_SUBDOMAIN = os.getenv("AMOCRM_SUBDOMAIN", "")
AMOCRM_LONG_LIVED_TOKEN = os.getenv("AMOCRM_LONG_LIVED_TOKEN", "")

def load_accounts():
    """Загружает список аккаунтов из accounts.json"""
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Ошибка чтения {ACCOUNTS_FILE}: {e}")
        return []

def save_accounts(accounts):
    """Сохраняет обновленный список аккаунтов в accounts.json"""
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
