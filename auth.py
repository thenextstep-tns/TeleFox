import os
import sys
import json
import asyncio
import argparse
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

from config import (
    BASE_DIR,
    SESSIONS_DIR,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_PHONE,
    TELEGRAM_2FA_PASSWORD,
    load_accounts,
    save_accounts,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

AUTH_STATE_FILE = SESSIONS_DIR / ".auth_state_{session_name}.json"

def get_state_file(session_name: str):
    return SESSIONS_DIR / f".auth_state_{session_name}.json"

def save_auth_state(session_name: str, data: dict):
    with open(get_state_file(session_name), "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_auth_state(session_name: str):
    state_file = get_state_file(session_name)
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def clear_auth_state(session_name: str):
    state_file = get_state_file(session_name)
    if state_file.exists():
        try:
            state_file.unlink()
        except OSError:
            pass

def register_session(session_name: str, me, phone: str):
    existing_accounts = load_accounts()
    account_entry = {
        "session_name": session_name,
        "phone": f"+{me.phone}" if me.phone and not str(me.phone).startswith("+") else (str(me.phone) or phone),
        "user_id": me.id,
        "username": me.username or "",
        "first_name": me.first_name or "",
        "is_active": True,
        "description": f"Аккаунт {me.first_name} (@{me.username or me.id})"
    }

    updated = False
    for i, acc in enumerate(existing_accounts):
        if acc.get("session_name") == session_name:
            existing_accounts[i] = account_entry
            updated = True
            break
    if not updated:
        existing_accounts.append(account_entry)

    save_accounts(existing_accounts)
    print(f"[+] Конфигурация успешно сохранена в accounts.json")

async def request_code(session_name: str, phone: str, api_id: int, api_hash: str):
    session_path = SESSIONS_DIR / session_name
    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"[!] Сессия '{session_name}' уже авторизована для пользователя: {me.first_name} (@{me.username})")
        register_session(session_name, me, phone)
        await client.disconnect()
        return

    print(f"[*] Отправка запроса кода на номер {phone}...")
    sent_code = await client.send_code_request(phone)
    save_auth_state(session_name, {
        "phone": phone,
        "phone_code_hash": sent_code.phone_code_hash,
        "session_name": session_name
    })
    await client.disconnect()
    print(f"[+] Код успешно отправлен на номер {phone}!")
    print(f"[*] Теперь введите код командой:")
    print(f"    python auth.py verify-code --code <КОД_ИЗ_ТЕЛЕГРАМА> --session {session_name}")

async def verify_code(session_name: str, code: str, password: str, api_id: int, api_hash: str):
    state = load_auth_state(session_name)
    if not state:
        print(f"[!] Ошибка: не найдено состояние авторизации для сессии '{session_name}'. Сначала вызовите 'request-code'.")
        return

    phone = state["phone"]
    phone_code_hash = state["phone_code_hash"]
    session_path = SESSIONS_DIR / session_name
    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        effective_password = password or TELEGRAM_2FA_PASSWORD or os.getenv("TELEGRAM_2FA_PASSWORD", "")
        if not effective_password:
            print("[*] Для аккаунта включена двухфакторная аутентификация (2FA).")
            print(f"[*] Пожалуйста, укажите пароль:")
            print(f"    python auth.py verify-code --code {code} --password <ВАШ_2FA_ПАРОЛЬ> --session {session_name}")
            await client.disconnect()
            return
        print("[*] Использование сохраненного 2FA пароля из .env...")
        await client.sign_in(password=effective_password)
    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
        print(f"[!] Ошибка ввода кода: {e}")
        await client.disconnect()
        return
    except Exception as e:
        print(f"[!] Ошибка авторизации: {e}")
        await client.disconnect()
        return

    me = await client.get_me()
    print("\n" + "=" * 60)
    print(f"[+] УСПЕШНО АВТОРИЗОВАН АККАУНТ:")
    print(f"    Имя: {me.first_name} {me.last_name or ''}")
    print(f"    Username: @{me.username}" if me.username else "    Username: (отсутствует)")
    print(f"    ID: {me.id}")
    print(f"    Телефон: +{me.phone}")
    print(f"    Файл сессии: {session_path}.session")
    print("=" * 60)

    register_session(session_name, me, phone)
    clear_auth_state(session_name)
    await client.disconnect()

async def check_status(api_id: int, api_hash: str):
    accounts = load_accounts()
    print("=" * 60)
    print("           СТАТУС ПОДКЛЮЧЕННЫХ СЕССИЙ")
    print("=" * 60)
    if not accounts:
        print("Нет сохраненных аккаунтов в accounts.json")
        return

    for acc in accounts:
        s_name = acc.get("session_name")
        s_path = SESSIONS_DIR / s_name
        try:
            client = TelegramClient(str(s_path), api_id, api_hash)
            await client.connect()
            is_auth = await client.is_user_authorized()
            if is_auth:
                me = await client.get_me()
                print(f"[АКТИВЕН] Сессия: {s_name:<12} | Пользователь: {me.first_name} (@{me.username or 'нет'}) | +{me.phone}")
            else:
                print(f"[НЕ АВТОРИЗОВАН] Сессия: {s_name:<12} | Телефон в конфиге: {acc.get('phone')}")
            await client.disconnect()
        except sqlite3.OperationalError:
            print(f"[АКТИВЕН / ОНЛАЙН] Сессия: {s_name:<12} | Работает в запущенной службе main.py (порт 5050)")

async def interactive_auth(api_id: int, api_hash: str):
    print("=" * 60)
    print("      ИНТЕРАКТИВНАЯ АВТОРИЗАЦИЯ АККАУНТА (TELETHON)")
    print("=" * 60)

    existing_accounts = load_accounts()
    default_session_name = f"account_{len(existing_accounts) + 1}"

    session_name = input(f"\nВведите имя для этой сессии (по умолчанию '{default_session_name}'): ").strip()
    if not session_name:
        session_name = default_session_name

    phone = input("Введите номер телефона (например +79991234567): ").strip()
    if not phone:
        print("[!] Номер телефона не может быть пустым.")
        return

    session_path = SESSIONS_DIR / session_name
    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"[*] Отправка кода на номер {phone}...")
        try:
            sent_code = await client.send_code_request(phone)
        except Exception as e:
            print(f"[!] Ошибка отправки кода: {e}")
            await client.disconnect()
            return

        code = input("Введите код подтверждения из Telegram: ").strip()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=sent_code.phone_code_hash)
        except SessionPasswordNeededError:
            pwd = input("Введите пароль двухфакторной аутентификации (2FA): ").strip()
            await client.sign_in(password=pwd)
        except Exception as e:
            print(f"[!] Ошибка авторизации: {e}")
            await client.disconnect()
            return

    me = await client.get_me()
    print("\n" + "=" * 60)
    print(f"[+] УСПЕШНО АВТОРИЗОВАН АККАУНТ: {me.first_name} (@{me.username or me.id}, +{me.phone})")
    print("=" * 60)
    register_session(session_name, me, phone)
    await client.disconnect()

def main():
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("[!] Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы в .env")
        sys.exit(1)

    api_id = int(TELEGRAM_API_ID)
    api_hash = TELEGRAM_API_HASH

    parser = argparse.ArgumentParser(description="Авторизация Telegram сессий для Telethon")
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    # request-code
    req_parser = subparsers.add_parser("request-code", help="Запросить код подтверждения на телефон")
    req_parser.add_argument("--phone", default=TELEGRAM_PHONE, help=f"Номер телефона (по умолчанию: {TELEGRAM_PHONE})")
    req_parser.add_argument("--session", default="account_1", help="Имя сессии (по умолчанию account_1)")

    # verify-code
    ver_parser = subparsers.add_parser("verify-code", help="Подтвердить полученный код")
    ver_parser.add_argument("--code", required=True, help="Код подтверждения")
    ver_parser.add_argument("--password", default=TELEGRAM_2FA_PASSWORD, help="2FA пароль (по умолчанию из .env)")
    ver_parser.add_argument("--session", default="account_1", help="Имя сессии")

    # status
    subparsers.add_parser("status", help="Проверить статус всех сессий")

    args = parser.parse_args()

    if args.command == "request-code":
        asyncio.run(request_code(args.session, args.phone, api_id, api_hash))
    elif args.command == "verify-code":
        asyncio.run(verify_code(args.session, args.code, args.password, api_id, api_hash))
    elif args.command == "status":
        asyncio.run(check_status(api_id, api_hash))
    else:
        asyncio.run(interactive_auth(api_id, api_hash))

if __name__ == "__main__":
    main()
