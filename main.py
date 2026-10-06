import os
import sys
import asyncio
import logging
from datetime import datetime
import uvicorn
from telethon import TelegramClient, events

from config import (
    WEB_PORT,
    SESSIONS_DIR,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    N8N_WEBHOOK_URL,
    load_accounts,
)
from uploader import send_to_n8n
from rules import apply_business_rules, is_chat_allowed, load_rules, passes_filters
from db import init_db, save_document, log_event, extract_vin, get_chat_category, CATEGORY_TITLES
from server import app, ACTIVE_CLIENTS, record_intercepted_doc, broadcast_event, media_kind, media_label
from telefox_service import (
    load_notification_settings,
    should_notify_for_message,
    dispatch_android_notification,
)
from telethon import errors as _tl_errors
from telethon.tl.types import updates as _tl_updates
import time as _time

# Защита от TypeNotFoundError в Telethon (неизвестные новые типы Telegram, например в форумах)
_orig_client_call = TelegramClient.__call__

async def _resilient_client_call(self, request, ordered=False):
    try:
        return await _orig_client_call(self, request, ordered=ordered)
    except _tl_errors.TypeNotFoundError as e:
        req_name = type(request).__name__
        logging.getLogger("TelethonRunner").warning(f"Игнорируем неизвестный объект Telegram ({e}) в {req_name}.")
        if "Difference" in req_name:
            if "Channel" in req_name:
                return _tl_updates.ChannelDifferenceEmpty(pts=getattr(request, "pts", 0), final=True, timeout=None)
            return _tl_updates.DifferenceEmpty(date=datetime.now(), seq=getattr(request, "pts", 0))
        return None

TelegramClient.__call__ = _resilient_client_call

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Настройка логирования
logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("TelethonRunner")

async def handle_incoming_media(
    client: TelegramClient,
    event: events.NewMessage.Event,
    account_info: dict,
    chat_type: str = "private",
    topic_id: int = None,
    chat_title: str = ""
):
    """
    Обработчик входящего сообщения с документом или фотографией
    """
    session_name = account_info.get("session_name")
    logger.info(f"[{session_name}] Обработка медиа ID={event.id} в чате {event.chat_id} (тип: {chat_type}, топик: {topic_id})")

    try:
        sender = await event.get_sender()
    except Exception as e:
        logger.warning(f"Не удалось получить информацию об отправителе: {e}")
        sender = None

    sender_id = sender.id if sender else event.sender_id
    sender_username = getattr(sender, "username", "") or ""
    sender_phone = getattr(sender, "phone", "") or ""
    first_name = getattr(sender, "first_name", "") or ""
    last_name = getattr(sender, "last_name", "") or ""

    # Категория чата/топика и проект
    topic_id_str = str(topic_id) if topic_id else None
    cat_info = await get_chat_category(str(event.chat_id), topic_id_str)
    category_id = cat_info.get("category_id") or cat_info.get("category", "none") if cat_info else "none"
    category_name = cat_info.get("category_name") or cat_info.get("category_title", "Без категории") if cat_info else "Без категории"
    project_id = cat_info.get("project_id", "") if cat_info else ""
    project_name = cat_info.get("project_name", "") if cat_info else ""
    project_type = cat_info.get("project_type", "general") if cat_info else "general"
    process_name = cat_info.get("process_name", "") if cat_info else ""
    custom_webhook = cat_info.get("webhook_url", "") if cat_info else ""

    # 1. Проверка белого/черного списка чатов
    rules = load_rules()
    is_allowed, reason = is_chat_allowed(event.chat_id, sender_username, rules, is_private=event.is_private)
    if not is_allowed:
        logger.info(f"[{session_name}] Чат {event.chat_id} (@{sender_username}) пропущен: {reason}")
        return

    sender_is_bot = bool(getattr(sender, "bot", False))

    filename = None
    mime_type = "application/octet-stream"

    if event.file:
        filename = event.file.name
        mime_type = event.file.mime_type or mime_type

    if not filename:
        if event.photo:
            filename = f"photo_{event.id}.jpg"
            mime_type = "image/jpeg"
        elif event.document:
            ext = getattr(event.file, "ext", ".bin") or ".bin"
            filename = f"document_{event.id}{ext}"

    filters_ok, filters_reason = passes_filters(filename, sender_is_bot, rules)
    if not filters_ok:
        logger.info(f"[{session_name}] Документ '{filename}' пропущен фильтрами: {filters_reason}")
        return

    caption = event.raw_text or ""
    detected_vin = extract_vin(caption) or extract_vin(filename)
    if detected_vin:
        logger.info(f"[{session_name}] Обнаружен VIN автомобиля: {detected_vin}")

    logger.info(f"[{session_name}] Отправитель: {first_name} {last_name} (@{sender_username}, тел: {sender_phone})")
    logger.info(f"[{session_name}] Скачивание файла '{filename}'...")

    try:
        file_bytes = await event.download_media(file=bytes)
        if not file_bytes:
            logger.error(f"Файл {filename} пустой или не удалось скачать.")
            return
    except Exception as e:
        logger.exception(f"Ошибка при скачивании файла: {e}")
        return

    metadata = {
        "sender_id": sender_id,
        "sender_phone": sender_phone,
        "sender_username": sender_username,
        "first_name": first_name,
        "last_name": last_name,
        "chat_id": event.chat_id,
        "chat_title": chat_title,
        "chat_type": chat_type,
        "topic_id": topic_id_str or "",
        "project": {
            "id": project_id or "",
            "name": project_name or "",
            "type": project_type or "general"
        },
        "process": {
            "name": process_name or "",
            "action": cat_info.get("action", "webhook") if cat_info else "webhook"
        },
        "project_id": project_id or "",
        "project_name": project_name or "",
        "project_type": project_type or "",
        "category_id": category_id or "none",
        "category_name": category_name or "Без категории",
        "category": category_id or "none",
        "category_title": category_name or "Без категории",
        "message_id": event.id,
        "caption": caption,
        "filename": filename,
        "mime_type": mime_type,
        "vin": detected_vin,
        "account_phone": account_info.get("phone", ""),
        "account_session": session_name
    }

    # 2. Дублирование документа и метаданных в MongoDB Atlas
    doc_db_id = await save_document(metadata, file_bytes=file_bytes, vin=detected_vin)
    if doc_db_id:
        metadata["db_id"] = doc_db_id
        logger.info(f"[+] [MongoDB] Документ сохранен в базе teamo (ID: {doc_db_id})")

    # 3. Отправка в n8n Webhook (на персональный URL категории или глобальный)
    target_webhook_url = custom_webhook.strip() if custom_webhook and custom_webhook.strip() else N8N_WEBHOOK_URL
    n8n_ok = await send_to_n8n(
        webhook_url=target_webhook_url,
        file_bytes=file_bytes,
        filename=filename,
        metadata=metadata,
        content_type=mime_type
    )

    metadata["n8n_status"] = "sent" if n8n_ok else "failed_or_offline"

    # Запись события отправки в n8n в MongoDB аудит
    await log_event(
        action_type="n8n_dispatch",
        actor=f"{first_name} (@{sender_username})",
        status="success" if n8n_ok else "warning",
        details=f"Отправка документа '{filename}' [Проект: {project_name or 'Общий'}, Категория: {category_name}] в n8n Webhook: {'Успешно' if n8n_ok else 'Оффлайн'}",
        vin=detected_vin,
        entity_type="document",
        entity_id=doc_db_id or str(event.id),
        extra={"filename": filename, "n8n_status": metadata["n8n_status"], "target_webhook": target_webhook_url}
    )

    # 4. Применение бизнес-правил (авто-ответ, пересылка, вебхук)
    rules_res = await apply_business_rules(client, event, metadata, filename)
    metadata["rules_actions"] = rules_res.get("actions", [])

    # 5. Фиксация в локальной памяти панели управления (порт 5050)
    record_intercepted_doc(metadata)

    # 6. Живое оповещение браузера через SSE
    await broadcast_event("new_document", {
        **metadata,
        "file_size": len(file_bytes),
        "db_id": doc_db_id,
        "date": datetime.now().strftime("%d.%m %H:%M:%S")
    })

async def run_single_client(account: dict, default_api_id: int, default_api_hash: str):
    """
    Запуск отдельного клиента Telethon для конкретной сессии
    """
    session_name = account.get("session_name")
    api_id = account.get("api_id") or default_api_id
    api_hash = account.get("api_hash") or default_api_hash

    if not api_id or not api_hash:
        logger.error(f"[{session_name}] Не указаны api_id/api_hash. Пропуск.")
        return

    session_path = SESSIONS_DIR / session_name
    client = TelegramClient(
        str(session_path), int(api_id), str(api_hash),
        connection_retries=-1, retry_delay=3, auto_reconnect=True,
    )

    await client.connect()
    if not await client.is_user_authorized():
        logger.error(f"[{session_name}] Сессия не авторизована! Запустите 'python auth.py'.")
        await client.disconnect()
        return

    me = await client.get_me()
    logger.info(f"[+] Сессия [{session_name}] авторизована: {me.first_name} (@{me.username or me.id}, +{me.phone})")

    ACTIVE_CLIENTS[session_name] = client

    # Живой слушатель всех входящих сообщений
    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event):
        try:
            sender = await event.get_sender()
        except Exception:
            sender = None

        sender_id = sender.id if sender else event.sender_id
        sender_username = getattr(sender, "username", "") or ""
        sender_name = ""
        if sender:
            first = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            sender_name = f"{first} {last}".strip() or getattr(sender, "title", "") or getattr(sender, "username", "")
        if not sender_name:
            sender_name = getattr(event, "chat_title", "") or "Клиент"

        kind = media_kind(event.message)
        has_media = kind is not None
        media_type = media_label(event.message)
        file_name = getattr(event.file, "name", None) if event.file else None
        vin = extract_vin(event.raw_text or "") or (extract_vin(file_name) if file_name else "")

        is_private = event.is_private
        is_forum = False
        chat_title = ""
        try:
            chat = await event.get_chat()
            is_forum = getattr(chat, 'forum', False)
            chat_title = getattr(chat, 'title', '') or getattr(chat, 'first_name', '')
        except Exception:
            pass

        if is_private:
            chat_type = "private"
        elif is_forum:
            chat_type = "forum"
        elif event.is_group:
            chat_type = "group"
        elif event.is_channel:
            chat_type = "channel"
        else:
            chat_type = "group"

        topic_id = None
        if event.message.reply_to and getattr(event.message.reply_to, "forum_topic", False):
            topic_id = event.message.reply_to.reply_to_top_id or event.message.reply_to.reply_to_msg_id

        # Категория чата/топика и проект
        try:
            # База может быть недоступна — уведомление не должно из-за этого зависать
            cat_info = await asyncio.wait_for(
                get_chat_category(str(event.chat_id), str(topic_id) if topic_id else None), timeout=CATEGORY_LOOKUP_TIMEOUT_SEC)
        except Exception:
            cat_info = None
        category_id = cat_info.get("category_id") or cat_info.get("category", "none") if cat_info else "none"
        category_name = cat_info.get("category_name") or cat_info.get("category_title", "Без категории") if cat_info else "Без категории"
        project_id = cat_info.get("project_id", "") if cat_info else ""
        project_name = cat_info.get("project_name", "") if cat_info else ""
        project_color = cat_info.get("project_color", "") if cat_info else ""
        category_color = cat_info.get("category_color", "") if cat_info else ""
        category_icon = cat_info.get("category_icon", "") if cat_info else ""

        # 1. Тэг "Мусор" (trash): автоматически отмечается как прочитанный в Telegram
        if category_id == "trash":
            try:
                await client.send_read_acknowledge(event.chat_id, max_id=event.id)
            except Exception as e:
                logger.debug(f"Не удалось авто-прочитать сообщение в {event.chat_id}: {e}")

        # 2. Мгновенная рассылка живого события в веб-панель (как в мессенджере в реальном времени)
        await broadcast_event("new_message", {
            "chat_id": str(event.chat_id),
            "id": event.id,
            "text": event.raw_text or "",
            "is_outgoing": event.out,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "sender_id": str(sender_id),
            "sender_avatar_url": f"/api/avatar/{session_name}/{sender_id}" if sender_id else None,
            "chat_type": chat_type,
            "topic_id": topic_id,
            "project_id": project_id,
            "project_name": project_name,
            "project_color": project_color,
            "category": category_id,
            "category_id": category_id,
            "category_name": category_name,
            "category_title": category_name,
            "category_color": category_color,
            "category_icon": category_icon,
            "has_media": has_media,
            "media_type": media_type,
            "media_kind": kind,
            "file_name": file_name,
            "vin": vin,
            "date": datetime.now().strftime("%d.%m %H:%M:%S"),
            "date_timestamp": datetime.now().timestamp()
        })

        # 2b. Настраиваемые уведомления TeleFox (Android 14 / PWA)
        try:
            notif_settings = load_notification_settings()
            msg_payload = {
                "chat_id": str(event.chat_id),
                "project_id": project_id,
                "category_id": category_id,
                "is_private": is_private,
                "is_forum": is_forum
            }
            if should_notify_for_message(msg_payload, notif_settings):
                p_prefix = f"[{project_name}] " if project_name else ""
                c_suffix = f" ({category_name})" if category_name and category_name != "Без категории" else ""
                notif_title = f"{p_prefix}{sender_name}{c_suffix}"
                body_text = event.raw_text or media_label(event.message) or "Входящее сообщение"
                dispatch_android_notification(notif_title, body_text, str(event.chat_id), notif_settings)
                # Рассылка в браузер для нативных Web Notifications
                await broadcast_event("native_notification", {
                    "title": notif_title,
                    "body": body_text[:120],
                    "chat_id": str(event.chat_id),
                    "sound": notif_settings.get("sound", True),
                    "vibrate": notif_settings.get("vibrate", True)
                })
        except Exception as e:
            logger.warning(f"Ошибка диспетчера уведомлений: {e}")

        # 3. Тэги "Личное" (personal) и "Мусор" (trash) блокируются в бизнес-процессах
        if category_id in ("trash", "personal"):
            logger.info(f"[{session_name}] Чат {event.chat_id} имеет тэг '{category_name}' -> бизнес-процессы заблокированы.")
            return

        # Если сообщение содержит документ или фото — запускаем пайплайн обработки
        if has_media:
            await handle_incoming_media(
                client, event, account,
                chat_type=chat_type,
                topic_id=topic_id,
                chat_title=chat_title
            )

    sync_task = asyncio.create_task(keep_in_sync(client, session_name))

    while True:
        try:
            await client.run_until_disconnected()
            break
        except Exception as e:
            logger.warning(f"[{session_name}] Переподключение клиента Telethon после: {e}")
            client._updates_error = None
            if hasattr(client, "_message_box"):
                try:
                    client._message_box.end_difference()
                except Exception:
                    pass
            await asyncio.sleep(RECONNECT_DELAY_SEC)
            try:
                if not client.is_connected():
                    await client.connect()
            except Exception:
                pass
    sync_task.cancel()
    logger.info(f"[{session_name}] Отключение сессии...")
    ACTIVE_CLIENTS.pop(session_name, None)
    await client.disconnect()

# На телефоне API с сессиями Telegram доступен только самому приложению.
BIND_HOST = "127.0.0.1" if os.environ.get("TELEFOX_DATA_DIR") else "0.0.0.0"
SYNC_INTERVAL_SEC = 60          # как часто проверять соединение и догружать пропущенное
CATCH_UP_TIMEOUT_SEC = 45       # максимум на одну догрузку обновлений
CATEGORY_LOOKUP_TIMEOUT_SEC = 3 # база категорий не должна задерживать уведомление
RECONNECT_DELAY_SEC = 2


async def keep_in_sync(client: TelegramClient, session_name: str):
    """Раз в минуту проверяет соединение и догружает пропущенные обновления."""
    while True:
        await asyncio.sleep(SYNC_INTERVAL_SEC)
        try:
            if not client.is_connected():
                logger.info(f"[{session_name}] Соединение потеряно, переподключаюсь...")
                await client.connect()
            await asyncio.wait_for(client.catch_up(), timeout=CATCH_UP_TIMEOUT_SEC)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[{session_name}] Синхронизация не удалась: {e}")


async def run_web_server(port: int = WEB_PORT):
    """Запуск FastAPI сервера панели управления на локальном порту"""
    config = uvicorn.Config(
        app=app,
        host=BIND_HOST,
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    logger.info(f"[*] Автономная веб-панель TeleFox запущена: http://127.0.0.1:{port}")
    await server.serve()

async def main():
    print("=" * 65)
    print("   TELEFOX AUTONOMOUS ENGINE")
    print("=" * 65)

    # 1. Запуск локального веб-сервера сразу же (WebView сможет подключиться за <500мс)
    web_task = asyncio.create_task(run_web_server())

    # 2. Инициализация базы данных в фоновом режиме (не блокируя веб-сервер)
    async def try_init_db():
        try:
            await init_db()
        except Exception as e:
            logger.warning(f"MongoDB init warning: {e}")
    asyncio.create_task(try_init_db())

    # 3. Запуск Telegram клиентов в защищенном режиме
    async def safe_client_task(acc, api_id, api_hash):
        try:
            await run_single_client(acc, api_id, api_hash)
        except Exception as e:
            logger.error(f"Сбой клиента {acc.get('session_name')}: {e}")

    from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, load_accounts, N8N_WEBHOOK_URL
    accounts = load_accounts()
    active_accounts = [acc for acc in accounts if acc.get("is_active", True) and acc.get("phone")]

    if not active_accounts:
        logger.warning("Нет активных настроенных аккаунтов в accounts.json.")
        logger.info("Авторизуйте аккаунт через TeleFox веб-интерфейс.")
    elif not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.error("TELEGRAM_API_ID и TELEGRAM_API_HASH не настроены в .env файле.")
    else:
        logger.info(f"Активных Telegram-аккаунтов: {len(active_accounts)}")
        logger.info(f"n8n Webhook: {N8N_WEBHOOK_URL}")
        for acc in active_accounts:
            asyncio.create_task(safe_client_task(acc, int(TELEGRAM_API_ID), TELEGRAM_API_HASH))

    # Регистрация динамического запуска сессий через Веб-API
    import server
    server.CLIENT_STARTER = lambda acc: asyncio.create_task(safe_client_task(acc, int(TELEGRAM_API_ID), TELEGRAM_API_HASH))

    # Ожидание работы веб-сервера
    await web_task

def ensure_writable_environment(data_dir: str):
    import shutil
    from pathlib import Path
    
    target_dir = Path(data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    src_dir = Path(__file__).resolve().parent
    
    # .env — конфигурация приложения, обновляется вместе с APK.
    # Остальное — данные пользователя (аккаунты, правила, кэши): копируем только при первом запуске.
    always_refresh = {".env"}
    for fname in [".env", "accounts.json", "rules.json", "projects_cache.json", "categories_cache.json"]:
        src_file = src_dir / fname
        dest_file = target_dir / fname
        if not src_file.exists():
            continue
        missing = not dest_file.exists() or dest_file.stat().st_size == 0
        if missing or fname in always_refresh:
            try:
                shutil.copy2(src_file, dest_file)
            except Exception as e:
                logger.warning(f"Не удалось скопировать {fname}: {e}")

    src_sessions = src_dir / "sessions"
    dest_sessions = target_dir / "sessions"
    try:
        dest_sessions.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Очистка устаревшей/конфликтующей сессии ПК (account_1) на телефоне
    for dead_file in dest_sessions.glob("*account_1*"):
        try:
            dead_file.unlink()
            logger.info(f"Очищен устаревший ключ account_1: {dead_file.name}")
        except Exception:
            pass

    if src_sessions.exists():
        for sfile in src_sessions.glob("*.session*"):
            dest_sfile = dest_sessions / sfile.name
            if not dest_sfile.exists() or dest_sfile.stat().st_size == 0:
                try:
                    shutil.copy2(sfile, dest_sfile)
                except Exception as e:
                    logger.warning(f"Не удалось скопировать {sfile.name}: {e}")
        for sfile in src_sessions.glob(".auth_state*"):
            dest_sfile = dest_sessions / sfile.name
            try:
                shutil.copy2(sfile, dest_sfile)
            except Exception:
                pass

def run_embedded(data_dir=None):
    if data_dir:
        os.environ["TELEFOX_DATA_DIR"] = data_dir
        ensure_writable_environment(data_dir)
        try:
            from config import reload_config
            reload_config(data_dir)
        except Exception as e:
            logger.warning(f"reload_config error: {e}")
        
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except Exception as e:
        logger.exception(f"Fatal error in run_embedded: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Работа службы остановлена.")
