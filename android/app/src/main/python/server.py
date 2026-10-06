import os
import json
import asyncio
import logging
import sqlite3
import aiohttp
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, Response, Query
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from telethon.tl.functions.messages import GetForumTopicsRequest

from config import (
    load_accounts,
    BASE_DIR,
    SESSIONS_DIR,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_PHONE,
    TELEGRAM_2FA_PASSWORD,
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from auth import (
    get_state_file,
    save_auth_state,
    load_auth_state,
    clear_auth_state,
    register_session,
)
from rules import load_rules, save_rules
from db import (
    get_audit_logs,
    get_documents,
    get_document_binary,
    save_deal_note,
    get_deal_notes,
    log_event,
    extract_vin,
    set_chat_category,
    get_chat_category,
    get_all_chat_categories,
    load_all_categories,
    CATEGORY_TITLES,
    create_project,
    get_projects,
    get_project,
    update_project,
    delete_project,
    set_chat_project,
    set_chat_project_and_category,
    add_project_category,
    update_project_category,
    delete_project_category,
    DEFAULT_PROJECT_TEMPLATES,
    _UNSET
)
from telefox_service import (
    load_notification_settings,
    save_notification_settings,
    dispatch_android_notification
)

logger = logging.getLogger("server")

app = FastAPI(title="Telethon Ops Dashboard", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).resolve().parent / "web"
if not WEB_DIR.exists():
    WEB_DIR = BASE_DIR / "web"
INDEX_HTML_PATH = WEB_DIR / "index.html"
if not INDEX_HTML_PATH.exists():
    INDEX_HTML_PATH = Path(__file__).resolve().parent / "web" / "index.html"

MEDIA_CACHE_DIR = BASE_DIR / "cache" / "media"
try:
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

AVATAR_CACHE_DIR = BASE_DIR / "cache" / "avatars"
try:
    AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

AVATAR_SEMAPHORE = asyncio.Semaphore(2)

ACTIVE_CLIENTS = {}
CLIENT_STARTER = None

LOG_BUFFER = deque(maxlen=300)
LOG_SUBSCRIBERS = set()
EVENT_SUBSCRIBERS = set()

INTERCEPTED_DOCUMENTS = deque(maxlen=100)
CACHE_READ_OUTBOX_MAX_ID = {}

async def broadcast_event(event_type: str, data: dict):
    """Широковещательная рассылка живых событий в браузер через SSE"""
    msg = {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    for q in list(EVENT_SUBSCRIBERS):
        try:
            q.put_nowait(msg)
        except Exception:
            pass

class SSELogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = {
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage()
            }
            LOG_BUFFER.append(log_entry)
            for q in list(LOG_SUBSCRIBERS):
                try:
                    q.put_nowait(log_entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

sse_handler = SSELogHandler()
sse_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(sse_handler)

def record_intercepted_doc(data: dict):
    doc_entry = {
        "id": data.get("message_id"),
        "filename": data.get("filename"),
        "mime_type": data.get("mime_type"),
        "sender_id": data.get("sender_id"),
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "sender_username": data.get("sender_username"),
        "sender_phone": data.get("sender_phone"),
        "account_session": data.get("account_session"),
        "vin": data.get("vin", ""),
        "n8n_status": data.get("n8n_status", "pending"),
        "rules_actions": data.get("rules_actions", []),
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }
    INTERCEPTED_DOCUMENTS.appendleft(doc_entry)

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def get_index():
    if INDEX_HTML_PATH.exists():
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return "<h1>Web Dashboard UI file not found</h1>"

@app.get("/manifest.json")
async def get_manifest():
    manifest_file = WEB_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(manifest_file, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/sw.js")
async def get_service_worker():
    sw_file = WEB_DIR / "sw.js"
    if sw_file.exists():
        return Response(
            content=sw_file.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Service-Worker-Allowed": "/",
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache"
            }
        )
    raise HTTPException(status_code=404, detail="Service worker not found")

@app.get("/icons/{filename}")
async def get_icon(filename: str):
    icon_file = WEB_DIR / "icons" / filename
    if icon_file.exists():
        media = "image/png" if filename.endswith(".png") else "image/jpeg"
        return FileResponse(icon_file, media_type=media)
    raise HTTPException(status_code=404, detail="Icon not found")

@app.get("/api/notifications/settings")
async def get_notifications_settings():
    return load_notification_settings()

@app.post("/api/notifications/settings")
async def post_notifications_settings(req: Request):
    data = await req.json()
    save_notification_settings(data)
    return {"status": "ok", "settings": load_notification_settings()}

@app.post("/api/notifications/test")
async def test_notification():
    settings = load_notification_settings()
    dispatch_android_notification(
        "TeleFox",
        "Тестовое уведомление",
        "test_chat",
        settings
    )
    await broadcast_event("native_notification", {
        "title": "TeleFox",
        "body": "Тестовое уведомление",
        "chat_id": "test_chat",
        "sound": settings.get("sound", True),
        "vibrate": settings.get("vibrate", True)
    })
    return {"status": "ok", "message": "Тестовое уведомление отправлено"}

@app.get("/api/status")
async def get_status():
    accounts = load_accounts()
    client_statuses = []
    for acc in accounts:
        s_name = acc.get("session_name")
        client = ACTIVE_CLIENTS.get(s_name)
        is_connected = client.is_connected() if client else False
        client_statuses.append({
            **acc,
            "connected": is_connected
        })
    return {
        "status": "online",
        "port": 5050,
        "accounts": client_statuses
    }

@app.get("/api/logs")
async def stream_logs():
    async def event_generator():
        queue = asyncio.Queue()
        LOG_SUBSCRIBERS.add(queue)
        try:
            for item in list(LOG_BUFFER)[-50:]:
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            LOG_SUBSCRIBERS.discard(queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/events")
async def stream_events():
    """Поток живых событий (сообщения, документы, эскалации) в реальном времени"""
    async def event_generator():
        queue = asyncio.Queue()
        EVENT_SUBSCRIBERS.add(queue)
        try:
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            EVENT_SUBSCRIBERS.discard(queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/auth/status")
async def get_auth_status(session: str = "telefox_mobile"):
    client = ACTIVE_CLIENTS.get(session)
    if client and client.is_connected():
        try:
            if await client.is_user_authorized():
                me = await client.get_me()
                return {
                    "authorized": True,
                    "session": session,
                    "user": {
                        "id": me.id,
                        "first_name": me.first_name,
                        "last_name": me.last_name or "",
                        "username": me.username or "",
                        "phone": me.phone
                    }
                }
        except Exception as e:
            if "AuthKeyDuplicated" in str(e):
                ACTIVE_CLIENTS.pop(session, None)
                s_file = (SESSIONS_DIR / session).with_suffix(".session")
                if s_file.exists():
                    try:
                        s_file.unlink()
                    except Exception:
                        pass

    # Check session file directly if not active in memory
    session_path = SESSIONS_DIR / session
    s_file = session_path.with_suffix(".session")
    if s_file.exists() and s_file.stat().st_size > 0:
        try:
            test_client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
            await test_client.connect()
            is_auth = await test_client.is_user_authorized()
            if is_auth:
                me = await test_client.get_me()
                await test_client.disconnect()
                return {
                    "authorized": True,
                    "session": session,
                    "user": {
                        "id": me.id,
                        "first_name": me.first_name,
                        "last_name": me.last_name or "",
                        "username": me.username or "",
                        "phone": me.phone
                    }
                }
            await test_client.disconnect()
        except Exception as e:
            logger.debug(f"Auth check failed for {session}: {e}")
            if "AuthKeyDuplicated" in str(e):
                try:
                    s_file.unlink()
                except Exception:
                    pass

    pending_state = load_auth_state(session)
    return {
        "authorized": False,
        "session": session,
        "phone": (pending_state or {}).get("phone") or TELEGRAM_PHONE,
        "has_pending_code": pending_state is not None
    }

@app.post("/api/auth/send-code")
async def send_code_api(req: Request):
    data = await req.json()
    session_name = data.get("session", "telefox_mobile").strip() or "telefox_mobile"
    phone = data.get("phone", "").strip() or TELEGRAM_PHONE
    if not phone:
        return {"success": False, "error": "Номер телефона не указан"}

    # Disconnect any existing client for this session
    existing_client = ACTIVE_CLIENTS.pop(session_name, None)
    if existing_client:
        try:
            await existing_client.disconnect()
        except Exception:
            pass

    # Всегда удаляем старый/отозванный файл сессии при запросе нового кода,
    # чтобы Telethon создал полностью НОВЫЙ, отдельный Auth Key (не конфликтующий с другими устройствами)
    session_path = SESSIONS_DIR / session_name
    s_file = session_path.with_suffix(".session")
    if s_file.exists():
        try:
            s_file.unlink()
            logger.info(f"Старый файл сессии {s_file.name} удален для генерации отдельного ключа")
        except Exception as e:
            logger.warning(f"Removing old session file: {e}")
    clear_auth_state(session_name)

    client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    try:
        try:
            await client.connect()
        except Exception as conn_err:
            if "AuthKeyDuplicated" in str(conn_err) or "AuthKey" in str(conn_err):
                logger.warning(f"Auth key conflict detected for {session_name}. Purging and creating fresh key...")
                if s_file.exists():
                    try:
                        s_file.unlink()
                    except Exception:
                        pass
                client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
                await client.connect()
            else:
                raise conn_err

        sent_code = await client.send_code_request(phone)
        save_auth_state(session_name, {
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "session_name": session_name
        })
        logger.info(f"Код подтверждения успешно запрошен с отдельным Auth Key ({session_name}) для {phone}")
        return {
            "success": True,
            "message": f"Код подтверждения отправлен в Telegram на номер {phone}",
            "phone": phone,
            "session": session_name
        }
    except Exception as e:
        logger.exception(f"Ошибка при отправке кода на {phone}: {e}")
        if s_file.exists():
            try:
                s_file.unlink()
            except Exception:
                pass
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

@app.post("/api/auth/verify-code")
async def verify_code_api(req: Request):
    data = await req.json()
    session_name = data.get("session", "telefox_mobile").strip() or "telefox_mobile"
    code = str(data.get("code", "")).strip()
    password = data.get("password", "").strip() or TELEGRAM_2FA_PASSWORD

    state = load_auth_state(session_name)
    if not state:
        return {
            "success": False,
            "error": "Не найдено состояние отправки кода. Сначала нажмите 'Запросить код'."
        }

    phone = state.get("phone")
    phone_code_hash = state.get("phone_code_hash")
    session_path = SESSIONS_DIR / session_name

    client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    try:
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return {
                    "success": False,
                    "needs_2fa": True,
                    "error": "Для входа требуется пароль двухфакторной аутентификации (2FA)."
                }
            await client.sign_in(password=password)
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
            return {
                "success": False,
                "error": f"Неверный или устаревший код: {e}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка авторизации: {e}"
            }

        me = await client.get_me()
        register_session(session_name, me, phone)
        clear_auth_state(session_name)

        user_info = {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name or "",
            "username": me.username or "",
            "phone": me.phone
        }
        logger.info(f"[+] Сессия {session_name} успешно авторизована: {me.first_name} (+{me.phone})")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    acc_entry = {
        "session_name": session_name,
        "phone": f"+{user_info['phone']}" if user_info.get("phone") and not str(user_info["phone"]).startswith("+") else (str(user_info.get("phone")) or phone),
        "user_id": user_info["id"],
        "username": user_info["username"],
        "first_name": user_info["first_name"],
        "is_active": True
    }
    if CLIENT_STARTER:
        try:
            CLIENT_STARTER(acc_entry)
        except Exception as e:
            logger.warning(f"CLIENT_STARTER error: {e}")

    await broadcast_event("auth_changed", {
        "session": session_name,
        "authorized": True,
        "user": user_info
    })

    return {
        "success": True,
        "message": f"Успешный вход: {user_info['first_name']} (@{user_info['username']})",
        "user": user_info
    }

@app.post("/api/auth/logout")
async def logout_api(req: Request):
    data = await req.json()
    session_name = data.get("session", "telefox_mobile").strip() or "telefox_mobile"
    client = ACTIVE_CLIENTS.pop(session_name, None)
    if client:
        try:
            await client.log_out()
        except Exception:
            try:
                await client.disconnect()
            except Exception:
                pass

    session_path = SESSIONS_DIR / session_name
    s_file = session_path.with_suffix(".session")
    if s_file.exists():
        try:
            s_file.unlink()
        except Exception:
            pass
    clear_auth_state(session_name)

    await broadcast_event("auth_changed", {
        "session": session_name,
        "authorized": False
    })
    return {"success": True, "message": f"Сессия {session_name} отключена"}

@app.get("/api/dialogs")
async def get_dialogs(
    session: str = "telefox_mobile",
    limit: int = 100,
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    category_id: Optional[str] = None
):
    if not ACTIVE_CLIENTS:
        for _ in range(10):
            await asyncio.sleep(0.2)
            if ACTIVE_CLIENTS:
                break

    client = ACTIVE_CLIENTS.get(session)
    if not client:
        if ACTIVE_CLIENTS:
            client = next(iter(ACTIVE_CLIENTS.values()))
        else:
            return {"dialogs": [], "warning": "Сессия Telegram не подключена. Войдите в аккаунт ниже.", "unauthorized": True}

    try:
        try:
            await load_all_categories()
        except Exception:
            pass
        dialogs = await client.get_dialogs(limit=limit)
        results = []
        for d in dialogs:
            if hasattr(d, 'dialog') and hasattr(d.dialog, 'read_outbox_max_id'):
                CACHE_READ_OUTBOX_MAX_ID[f"{session}:{d.id}"] = d.dialog.read_outbox_max_id or 0
            title = d.title or getattr(d.entity, 'first_name', '') or 'Диалог'
            last_msg = ""
            if d.message:
                if d.message.text:
                    last_msg = d.message.text[:80]
                elif d.message.photo:
                    last_msg = "📷 Фотография"
                elif d.message.document:
                    last_msg = f"📄 Документ ({getattr(d.message.file, 'name', 'файл')})"

            username = getattr(d.entity, 'username', '') or ''
            is_forum = getattr(d.entity, 'forum', False)

            if d.is_user:
                chat_type = "private"
            elif is_forum:
                chat_type = "forum"
            elif d.is_group:
                chat_type = "group"
            elif d.is_channel:
                chat_type = "channel"
            else:
                chat_type = "group"

            # Категория и проект чата из базы
            cat_info = await get_chat_category(str(d.id))
            chat_project_id = cat_info.get("project_id") if cat_info else None
            chat_project_name = cat_info.get("project_name") if cat_info else None
            chat_project_type = cat_info.get("project_type") if cat_info else None
            chat_project_color = cat_info.get("project_color") if cat_info else None
            c_id = cat_info.get("category_id") or cat_info.get("category", "none") if cat_info else "none"
            c_name = cat_info.get("category_name") or cat_info.get("category_title", "Без категории") if cat_info else "Без категории"
            c_color = cat_info.get("category_color") if cat_info else None
            c_icon = cat_info.get("category_icon") if cat_info else None
            p_process = cat_info.get("process_name") if cat_info else None

            date_ts = float(d.date.timestamp()) if d.date else 0.0
            unread_cnt = d.unread_count or 0

            results.append({
                "id": str(d.id),
                "title": title,
                "username": username,
                "is_user": d.is_user,
                "is_group": d.is_group,
                "is_channel": d.is_channel,
                "is_forum": is_forum,
                "chat_type": chat_type,
                "project_id": chat_project_id,
                "project_name": chat_project_name,
                "project_type": chat_project_type,
                "project_color": chat_project_color,
                "category": c_id,
                "category_id": c_id,
                "category_name": c_name,
                "category_title": c_name,
                "category_color": c_color,
                "category_icon": c_icon,
                "process_name": p_process,
                "unread_count": unread_cnt,
                "last_message": last_msg,
                "date": d.date.strftime("%d.%m %H:%M") if d.date else "",
                "date_timestamp": date_ts,
                "avatar_url": f"/api/avatar/{session}/{d.id}"
            })

        # 1. Фильтрация по проекту
        if project_id:
            if project_id == "unassigned":
                results = [d for d in results if not d.get("project_id")]
            elif project_id != "all":
                results = [d for d in results if d.get("project_id") == project_id]

        # 2. Фильтрация по категории
        if category_id and category_id != "all":
            results = [d for d in results if (d.get("category_id") == category_id or d.get("category") == category_id)]

        # 3. Сортировка: непрочитанные (кроме мусора) первыми, затем самые свежие по времени сообщения
        def dialog_sort_key(item):
            cat = item.get("category", "none")
            has_unread = 0 if (item.get("unread_count", 0) > 0 and cat != "trash") else 1
            ts_inv = -item.get("date_timestamp", 0.0)
            return (has_unread, ts_inv)

        results.sort(key=dialog_sort_key)

        # 4. Поиск по ключевым словам (если задан)
        if q:
            q_clean = q.lower().strip()
            results = [
                d for d in results
                if q_clean in d["title"].lower()
                or q_clean in d.get("username", "").lower()
                or q_clean in d.get("last_message", "").lower()
                or q_clean in d.get("category_title", "").lower()
                or q_clean in (d.get("project_name") or "").lower()
                or q_clean in str(d["id"])
            ]

        return {"dialogs": results}
    except Exception as e:
        logger.error(f"Ошибка получения диалогов: {e}")
        return {"dialogs": [], "error": str(e)}

@app.get("/api/dialogs/{chat_id}/topics")
async def get_dialog_topics(chat_id: str, session: str = "account_1"):
    """
    Возвращает список топиков (веток) форум-супергруппы
    """
    if not ACTIVE_CLIENTS:
        for _ in range(15):
            await asyncio.sleep(0.3)
            if ACTIVE_CLIENTS:
                break

    client = ACTIVE_CLIENTS.get(session)
    if not client:
        if ACTIVE_CLIENTS:
            client = next(iter(ACTIVE_CLIENTS.values()))
        else:
            return {"topics": [], "warning": "Нет подключенных активных клиентов"}

    try:
        try:
            c_id = int(chat_id)
        except ValueError:
            c_id = chat_id

        entity = await client.get_entity(c_id)
        is_forum = getattr(entity, 'forum', False)
        if not is_forum:
            return {"topics": [], "is_forum": False}

        res = await client(GetForumTopicsRequest(
            peer=entity,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=100
        ))

        topics_list = []
        for t in res.topics:
            topic_id_str = str(t.id)
            cat_info = await get_chat_category(str(chat_id), topic_id_str)
            topic_c_id = cat_info.get("category_id") or cat_info.get("category", "none") if cat_info else "none"
            topic_c_name = cat_info.get("category_name") or cat_info.get("category_title", "Без категории") if cat_info else "Без категории"
            topic_c_color = cat_info.get("category_color") if cat_info else None
            topic_c_icon = cat_info.get("category_icon") if cat_info else None
            topic_project_id = cat_info.get("project_id") if cat_info else None
            topic_project_name = cat_info.get("project_name") if cat_info else None
            topic_project_color = cat_info.get("project_color") if cat_info else None
            topic_process_name = cat_info.get("process_name") if cat_info else None

            topics_list.append({
                "id": t.id,
                "title": getattr(t, "title", f"Топик {t.id}"),
                "icon_color": getattr(t, "icon_color", 0),
                "closed": getattr(t, "closed", False),
                "unread_count": getattr(t, "unread_count", 0),
                "category": topic_c_id,
                "category_id": topic_c_id,
                "category_name": topic_c_name,
                "category_title": topic_c_name,
                "category_color": topic_c_color,
                "category_icon": topic_c_icon,
                "project_id": topic_project_id,
                "project_name": topic_project_name,
                "project_color": topic_project_color,
                "process_name": topic_process_name
            })

        return {"topics": topics_list, "is_forum": True}
    except Exception as e:
        logger.error(f"Ошибка получения топиков форума {chat_id}: {e}")
        return {"topics": [], "error": str(e)}

@app.get("/api/dialogs/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    session: str = "account_1",
    topic_id: Optional[int] = None,
    limit: int = 50
):
    if not ACTIVE_CLIENTS:
        for _ in range(15):
            await asyncio.sleep(0.3)
            if ACTIVE_CLIENTS:
                break

    client = ACTIVE_CLIENTS.get(session)
    if not client:
        if ACTIVE_CLIENTS:
            client = next(iter(ACTIVE_CLIENTS.values()))
        else:
            return {"messages": [], "warning": "Нет подключенных активных клиентов"}

    try:
        try:
            entity_id = int(chat_id)
        except ValueError:
            entity_id = chat_id

        if topic_id:
            messages = await client.get_messages(entity_id, reply_to=topic_id, limit=limit)
        else:
            messages = await client.get_messages(entity_id, limit=limit)

        cache_key = f"{session}:{entity_id}"
        read_outbox_max_id = CACHE_READ_OUTBOX_MAX_ID.get(cache_key, 0)
        if not read_outbox_max_id:
            try:
                dialogs_peek = await asyncio.wait_for(client.get_dialogs(limit=1, offset_peer=entity_id), timeout=1.5)
                if dialogs_peek and hasattr(dialogs_peek[0], 'dialog') and hasattr(dialogs_peek[0].dialog, 'read_outbox_max_id'):
                    read_outbox_max_id = dialogs_peek[0].dialog.read_outbox_max_id or 0
                    CACHE_READ_OUTBOX_MAX_ID[cache_key] = read_outbox_max_id
            except Exception:
                pass

        results = []
        for m in reversed(messages):
            has_media = bool(m.photo or m.document)
            is_photo = bool(m.photo)
            is_document = bool(m.document and not m.photo)
            media_type = "Фото" if is_photo else ("Документ" if is_document else None)
            file_name = getattr(m.file, "name", None) if m.file else None

            # Автор сообщения
            sender = m.sender
            sender_id = str(m.sender_id) if m.sender_id else ""
            sender_name = ""
            sender_username = ""

            if sender:
                first = getattr(sender, "first_name", "") or ""
                last = getattr(sender, "last_name", "") or ""
                sender_name = f"{first} {last}".strip() or getattr(sender, "title", "") or getattr(sender, "username", "")
                sender_username = getattr(sender, "username", "") or ""
            elif getattr(m, "post_author", None):
                sender_name = m.post_author
            elif m.out:
                sender_name = "Вы"
            elif sender_id:
                sender_name = f"Участник {sender_id}"
            else:
                sender_name = "Участник"

            is_read = bool(m.out and read_outbox_max_id and m.id <= read_outbox_max_id)

            results.append({
                "id": m.id,
                "text": m.text or "",
                "is_outgoing": m.out,
                "is_read": is_read,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "sender_username": sender_username,
                "sender_avatar_url": f"/api/avatar/{session}/{sender_id}" if sender_id else None,
                "has_media": has_media,
                "is_photo": is_photo,
                "is_document": is_document,
                "media_type": media_type,
                "file_name": file_name,
                "media_url": f"/api/media/{session}/{chat_id}/{m.id}" if has_media else None,
                "vin": extract_vin(m.text or "") or (extract_vin(file_name) if file_name else ""),
                "reply_to_msg_id": getattr(m, "reply_to_msg_id", None),
                "date": m.date.strftime("%d.%m %H:%M:%S") if m.date else "",
                "date_timestamp": float(m.date.timestamp()) if m.date else 0.0
            })
        # Строгая сортировка по времени (от старых к новым)
        results.sort(key=lambda x: (x.get("date_timestamp", 0.0), x.get("id", 0)))
        return {"messages": results, "topic_id": topic_id}
    except Exception as e:
        logger.error(f"Ошибка получения сообщений: {e}")
        return {"messages": [], "error": str(e)}

@app.get("/api/media/{session}/{chat_id}/{message_id}")
async def get_message_media(session: str, chat_id: str, message_id: int):
    """
    Загрузка и отдача изображений/файлов из Telegram с кэшированием на диск
    """
    # 1. Проверяем локальный кэш
    matches = list(MEDIA_CACHE_DIR.glob(f"{session}_{chat_id}_{message_id}.*"))
    if matches:
        cache_file = matches[0]
        ext = cache_file.suffix.lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else ("image/png" if ext == ".png" else "application/octet-stream")
        with open(cache_file, "rb") as f:
            return Response(content=f.read(), media_type=mime)

    # 2. Скачиваем через Telethon
    client = ACTIVE_CLIENTS.get(session)
    if not client:
        if ACTIVE_CLIENTS:
            client = next(iter(ACTIVE_CLIENTS.values()))
        else:
            raise HTTPException(status_code=404, detail="Нет активных Telegram клиентов")

    try:
        try:
            c_id = int(chat_id)
        except ValueError:
            c_id = chat_id

        msg = await client.get_messages(c_id, ids=message_id)
        if not msg or not (msg.photo or msg.document):
            raise HTTPException(status_code=404, detail="В сообщении нет медиафайла")

        ext = ".jpg" if msg.photo else (getattr(msg.file, "ext", ".bin") or ".bin")
        target_path = MEDIA_CACHE_DIR / f"{session}_{chat_id}_{message_id}{ext}"

        await client.download_media(msg, file=str(target_path))

        mime = "image/jpeg" if ext.lower() in (".jpg", ".jpeg") else (getattr(msg.file, "mime_type", "application/octet-stream") or "application/octet-stream")
        with open(target_path, "rb") as f:
            content = f.read()

        return Response(content=content, media_type=mime)
    except Exception as e:
        logger.error(f"Ошибка загрузки медиа {chat_id}/{message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/avatar/{session}/{entity_id}")
async def get_entity_avatar(session: str, entity_id: str):
    """
    Загрузка и отдача аватарки профиля пользователя или группы с кэшированием на диск
    """
    # 1. Проверяем кэш отсутствия аватарки (чтобы не спамить Telegram API повторными запросами)
    none_marker = AVATAR_CACHE_DIR / f"{session}_{entity_id}.none"
    if none_marker.exists():
        if (datetime.now().timestamp() - none_marker.stat().st_mtime) < 3600:
            raise HTTPException(status_code=404, detail="Аватар отсутствует")

    # 2. Проверяем наличие скачанного файла аватарки
    target_path = AVATAR_CACHE_DIR / f"{session}_{entity_id}.jpg"
    if target_path.exists() and target_path.stat().st_size > 0:
        with open(target_path, "rb") as f:
            return Response(
                content=f.read(),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"}
            )

    # 3. Скачиваем через Telethon
    client = ACTIVE_CLIENTS.get(session)
    if not client:
        if ACTIVE_CLIENTS:
            client = next(iter(ACTIVE_CLIENTS.values()))
        else:
            raise HTTPException(status_code=404, detail="Нет активных Telegram клиентов")

    try:
        try:
            e_id = int(entity_id)
        except ValueError:
            e_id = entity_id

        entity = await client.get_entity(e_id)
        if not getattr(entity, 'photo', None):
            none_marker.touch()
            raise HTTPException(status_code=404, detail="У пользователя/группы нет фото")

        async with AVATAR_SEMAPHORE:
            photo_path = await asyncio.wait_for(
                client.download_profile_photo(entity, file=str(target_path), download_big=False),
                timeout=5.0
            )

        if photo_path and target_path.exists() and target_path.stat().st_size > 0:
            with open(target_path, "rb") as f:
                return Response(
                    content=f.read(),
                    media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"}
                )
        else:
            none_marker.touch()
            raise HTTPException(status_code=404, detail="У пользователя/группы нет фото")
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Не удалось загрузить аватар {entity_id}: {e}")
        none_marker.touch()
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/intercepted")
async def get_intercepted_list():
    return {"items": list(INTERCEPTED_DOCUMENTS)}

# ----------------- MongoDB Atlas API -----------------

@app.get("/api/db/logs")
async def api_get_audit_logs(
    vin: str = "",
    action_type: str = "",
    status: str = "",
    level: str = "",
    actor: str = "",
    search: str = "",
    start_date: str = "",
    end_date: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """Выборка исторических логов из MongoDB с полной фильтрацией"""
    items, total = await get_audit_logs(
        vin=vin,
        action_type=action_type,
        status=status,
        level=level,
        actor=actor,
        search=search,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}

@app.get("/api/db/documents")
async def api_get_documents(
    vin: str = "",
    sender: str = "",
    search: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """Выборка сохраненных документов из MongoDB"""
    items, total = await get_documents(
        vin=vin,
        sender=sender,
        search=search,
        skip=skip,
        limit=limit
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}

@app.get("/api/db/documents/{doc_id}/download")
async def api_download_document(doc_id: str):
    """Скачивание бинарного файла документа из MongoDB"""
    doc = await get_document_binary(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден или бинарные данные отсутствуют")

    file_bytes, filename, mime_type = doc
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_bytes))
        }
    )

@app.post("/api/actions/escalate")
async def api_escalate_message(payload: dict):
    """Эскалация сообщения супервайзеру/руководству"""
    chat_id = payload.get("chat_id")
    message_id = payload.get("message_id")
    text = payload.get("text", "")
    author = payload.get("author", "Менеджер")
    vin = payload.get("vin", "")

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")

    note_id = await save_deal_note(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        note_type="escalation",
        author=author,
        vin=vin
    )

    # Оповещаем UI в реальном времени
    await broadcast_event("escalation", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "note_id": note_id,
        "author": author
    })

    return {"status": "success", "note_id": note_id}

@app.post("/api/actions/create_note")
async def api_create_deal_note(payload: dict):
    """Создание заметки к сделке (для фиксации в amoCRM / БД)"""
    chat_id = payload.get("chat_id")
    message_id = payload.get("message_id")
    text = payload.get("text", "")
    author = payload.get("author", "Менеджер")
    vin = payload.get("vin", "")

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")

    note_id = await save_deal_note(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        note_type="note",
        author=author,
        vin=vin
    )

    await broadcast_event("deal_note", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "note_id": note_id,
        "author": author
    })

    return {"status": "success", "note_id": note_id}

@app.get("/api/db/notes")
async def api_get_deal_notes(chat_id: str = "", note_type: str = ""):
    notes = await get_deal_notes(chat_id=chat_id, note_type=note_type)
    return {"notes": notes}

# ----------------- Бизнес-правила и чаты -----------------

@app.get("/api/rules")
async def get_business_rules():
    return load_rules()

@app.post("/api/rules")
async def update_business_rules(payload: dict):
    save_rules(payload)
    await log_event(
        action_type="rules_updated",
        actor="Менеджер (UI)",
        details="Бизнес-правила обновлены через веб-интерфейс"
    )
    return {"status": "success", "rules": payload}

@app.post("/api/chats/whitelist")
async def add_to_whitelist(payload: dict):
    target = payload.get("identifier")
    if not target:
        raise HTTPException(status_code=400, detail="Identifier is required")
    rules = load_rules()
    scope = rules.setdefault("chat_scope", {"mode": "all_private", "allowed_chats": [], "ignored_chats": []})
    allowed = scope.setdefault("allowed_chats", [])
    if target not in allowed:
        allowed.append(target)
    if target in scope.get("ignored_chats", []):
        scope["ignored_chats"].remove(target)
    save_rules(rules)
    await log_event(
        action_type="chat_whitelisted",
        actor="Менеджер (UI)",
        details=f"Чат '{target}' добавлен в Белый список"
    )
    return {"status": "success", "chat_scope": scope}

@app.post("/api/chats/blacklist")
async def add_to_blacklist(payload: dict):
    target = payload.get("identifier")
    if not target:
        raise HTTPException(status_code=400, detail="Identifier is required")
    rules = load_rules()
    scope = rules.setdefault("chat_scope", {"mode": "all_private", "allowed_chats": [], "ignored_chats": []})
    ignored = scope.setdefault("ignored_chats", [])
    if target not in ignored:
        ignored.append(target)
    if target in scope.get("allowed_chats", []):
        scope["allowed_chats"].remove(target)
    save_rules(rules)
    await log_event(
        action_type="chat_blacklisted",
        actor="Менеджер (UI)",
        details=f"Чат '{target}' добавлен в Черный список (игнорирование)"
    )
    return {"status": "success", "chat_scope": scope}

@app.post("/api/chats/category")
async def update_chat_category(payload: dict):
    """
    Назначение бизнес-роли чату или топику:
    'client' - Клиент
    'broker' - Брокер
    'logist' - Логист
    'customs' - Таможня
    'internal_client' - Внутренний Клиент
    'none' - Без категории
    При назначении категории чат автоматически добавляется в белый список правил.
    """
    chat_id = payload.get("chat_id")
    topic_id = payload.get("topic_id")
    category = payload.get("category", "none")
    title = payload.get("title", "")
    actor = payload.get("actor", "Менеджер (UI)")

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")

    topic_id_str = str(topic_id) if topic_id else None

    project_id = payload.get("project_id")

    # 1. Сохраняем категорию в БД / кэше
    cat_doc = await set_chat_category(
        chat_id=str(chat_id),
        category=category,
        topic_id=topic_id_str,
        title=title,
        assigned_by=actor,
        project_id=project_id
    )

    # 2. Обработка категорий в правилах и Telegram
    whitelisted = False
    blacklisted = False
    marked_read = False

    rules = load_rules()
    scope = rules.setdefault("chat_scope", {"mode": "all_private", "allowed_chats": [], "ignored_chats": []})
    allowed = scope.setdefault("allowed_chats", [])
    ignored = scope.setdefault("ignored_chats", [])
    c_id_str = str(chat_id)

    if category in ("personal", "trash"):
        # Тэги "Личное" и "Мусор" добавляются в черный список процессов
        if c_id_str not in ignored:
            ignored.append(c_id_str)
            blacklisted = True
        if c_id_str in allowed:
            allowed.remove(c_id_str)
        save_rules(rules)

        # Тэг "Мусор" автоматически отмечается как прочитанный в Telegram
        if category == "trash":
            client = ACTIVE_CLIENTS.get(payload.get("session", "account_1"))
            if not client and ACTIVE_CLIENTS:
                client = next(iter(ACTIVE_CLIENTS.values()))
            if client:
                try:
                    try:
                        c_id = int(chat_id)
                    except ValueError:
                        c_id = chat_id
                    await client.send_read_acknowledge(c_id)
                    marked_read = True
                except Exception as e:
                    logger.warning(f"Ошибка отметки прочитанным {chat_id}: {e}")

    elif category in ("client", "broker", "logist", "customs"):
        # Бизнес-категории белого списка процессов
        if c_id_str not in allowed:
            allowed.append(c_id_str)
            whitelisted = True
        if c_id_str in ignored:
            ignored.remove(c_id_str)
        save_rules(rules)

    elif category == "internal_client":
        # Внутренний клиент НЕ добавляется в белый список автоматом
        if c_id_str in allowed:
            allowed.remove(c_id_str)
        if c_id_str in ignored:
            ignored.remove(c_id_str)
        save_rules(rules)

    elif category == "none":
        if c_id_str in allowed:
            allowed.remove(c_id_str)
        if c_id_str in ignored:
            ignored.remove(c_id_str)
        save_rules(rules)

    # 3. Аудит-лог
    cat_title = CATEGORY_TITLES.get(category, category)
    target_desc = f"чат {chat_id}" + (f" (топик {topic_id})" if topic_id else "")
    audit_text = f"Назначена категория '{cat_title}' для {target_desc}."
    if blacklisted:
        audit_text += " Чат добавлен в ЧЕРНЫЙ список процессов (игнорирование)."
    elif whitelisted:
        audit_text += " Чат автоматически добавлен в белый список процессов."
    if marked_read:
        audit_text += " Чат автоматически отмечен как прочитанный в Telegram."

    await log_event(
        action_type="category_assigned",
        actor=actor,
        status="success",
        details=audit_text,
        extra={
            "chat_id": str(chat_id),
            "topic_id": topic_id_str,
            "category": category,
            "whitelisted": whitelisted,
            "blacklisted": blacklisted,
            "marked_read": marked_read
        }
    )

    # 4. SSE-оповещение клиентам
    await broadcast_event("category_updated", {
        "chat_id": str(chat_id),
        "topic_id": topic_id_str,
        "category": category,
        "category_title": cat_title,
        "marked_read": marked_read
    })

    return {
        "status": "success",
        "category": category,
        "category_title": cat_title,
        "whitelisted": whitelisted,
        "blacklisted": blacklisted,
        "marked_read": marked_read
    }

@app.post("/api/chat/bind")
async def api_bind_chat(payload: Dict[str, Any]):
    """Привязка чата или топика к проекту и категории с подтягиванием процесса n8n"""
    chat_id = payload.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")

    project_id = payload.get("project_id") if "project_id" in payload else _UNSET
    category_id = payload.get("category_id") if "category_id" in payload else _UNSET
    topic_id = payload.get("topic_id")
    title = payload.get("title", "")

    topic_id_str = str(topic_id) if topic_id else None
    result = await set_chat_project_and_category(
        chat_id=str(chat_id),
        project_id=project_id,
        category_id=category_id,
        topic_id=topic_id_str,
        title=title
    )

    p_name = result.get("project_name") or "Без проекта"
    c_name = result.get("category_name") or "Без категории"
    target_desc = f"чат {chat_id}" + (f" (топик {topic_id})" if topic_id else "")
    await log_event(
        action_type="chat_bound",
        actor="Менеджер",
        status="success",
        details=f"Чат {target_desc} привязан: Проект '{p_name}', Категория '{c_name}'",
        entity_type="project",
        entity_id=str(result.get("project_id") or ""),
        chat_id=str(chat_id)
    )

    if result.get("category_id") == "trash" or result.get("category") == "trash":
        try:
            for client in ACTIVE_CLIENTS.values():
                c_peer = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
                await client.send_read_acknowledge(c_peer)
        except Exception as e:
            logger.warning(f"Auto mark read for trash chat {chat_id} failed: {e}")

    await broadcast_event("project_updated", {
        "chat_id": str(chat_id),
        "topic_id": topic_id_str,
        "project_id": result.get("project_id"),
        "project_name": result.get("project_name"),
        "project_color": result.get("project_color"),
        "category_id": result.get("category_id"),
        "category_name": result.get("category_name"),
        "category_color": result.get("category_color"),
        "category_icon": result.get("category_icon"),
        "process_name": result.get("process_name")
    })

    return {"status": "success", "chat_id": chat_id, "bound": result}

@app.post("/api/chat/project")
async def api_set_chat_project(payload: Dict[str, Any]):
    """Привязка чата или топика к проекту (с сохранением существующей категории)"""
    chat_id = payload.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")

    project_id = payload.get("project_id") if "project_id" in payload else _UNSET
    topic_id = payload.get("topic_id")

    topic_id_str = str(topic_id) if topic_id else None
    result = await set_chat_project(str(chat_id), project_id=project_id, topic_id=topic_id_str)

    p_name = result.get("project_name") or "Без проекта"
    target_desc = f"чат {chat_id}" + (f" (топик {topic_id})" if topic_id else "")
    await log_event(
        action_type="project_assigned",
        actor="Менеджер",
        status="success",
        details=f"Чат {target_desc} привязан к проекту '{p_name}'",
        entity_type="project",
        entity_id=str(project_id or ""),
        chat_id=str(chat_id)
    )

    await broadcast_event("project_updated", {
        "chat_id": str(chat_id),
        "topic_id": topic_id_str,
        "project_id": result.get("project_id"),
        "project_name": result.get("project_name"),
        "project_color": result.get("project_color"),
        "category_id": result.get("category_id"),
        "category_name": result.get("category_name")
    })

    return {"status": "success", "chat_id": chat_id, "project": result}

@app.get("/api/projects")
async def api_get_projects(status: Optional[str] = None):
    projects = await get_projects(status=status)
    return {"projects": projects, "templates": DEFAULT_PROJECT_TEMPLATES}

@app.post("/api/projects")
async def api_create_project(payload: Dict[str, Any]):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Название проекта обязательно")
    project_type = payload.get("type", "custom")
    customer = payload.get("customer", "").strip()
    description = payload.get("description", "").strip()
    color = payload.get("color", "#38bdf8")
    template = payload.get("template")
    categories = payload.get("categories")

    project = await create_project(
        name=name,
        project_type=project_type,
        customer=customer,
        description=description,
        color=color,
        categories=categories,
        template=template
    )
    await log_event(
        action_type="project_created",
        actor="Менеджер",
        status="success",
        details=f"Создан новый проект '{name}' (Тип: {project_type}, Заказчик: {customer or 'не указан'})",
        entity_type="project",
        entity_id=project["id"]
    )
    return {"status": "success", "project": project}

@app.put("/api/projects/{project_id}")
async def api_update_project(project_id: str, payload: Dict[str, Any]):
    ok = await update_project(project_id, payload)
    if not ok:
        raise HTTPException(status_code=404, detail="Проект не найден или нет изменений")
    return {"status": "success"}

@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: str):
    ok = await delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Проект не найден")
    await log_event(
        action_type="project_deleted",
        actor="Менеджер",
        status="warning",
        details=f"Удален проект ID: {project_id}",
        entity_type="project",
        entity_id=project_id
    )
    return {"status": "success"}

@app.post("/api/projects/{project_id}/categories")
async def api_add_project_category(project_id: str, payload: Dict[str, Any]):
    cat = await add_project_category(project_id, payload)
    if not cat:
        raise HTTPException(status_code=400, detail="Не удалось добавить категорию")
    return {"status": "success", "category": cat}

@app.put("/api/projects/{project_id}/categories/{cat_id}")
async def api_update_project_category(project_id: str, cat_id: str, payload: Dict[str, Any]):
    ok = await update_project_category(project_id, cat_id, payload)
    if not ok:
        raise HTTPException(status_code=404, detail="Категория не найдена или нет изменений")
    return {"status": "success"}

@app.delete("/api/projects/{project_id}/categories/{cat_id}")
async def api_delete_project_category(project_id: str, cat_id: str):
    ok = await delete_project_category(project_id, cat_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return {"status": "success"}

@app.post("/api/messages/send")
async def api_send_message(payload: dict):
    """
    Отправка нового сообщения или ответа на конкретное сообщение через Telethon
    """
    chat_id = payload.get("chat_id")
    text = payload.get("text", "").strip()
    reply_to_msg_id = payload.get("reply_to_msg_id")
    topic_id = payload.get("topic_id")
    session = payload.get("session", "account_1")

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")
    if not text:
        raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")

    client = ACTIVE_CLIENTS.get(session)
    if not client:
        if ACTIVE_CLIENTS:
            client = next(iter(ACTIVE_CLIENTS.values()))
        else:
            raise HTTPException(status_code=404, detail="Нет активных Telegram клиентов")

    try:
        try:
            c_id = int(chat_id)
        except ValueError:
            c_id = chat_id

        # Если задан reply_to_msg_id — отвечаем на это сообщение
        # Иначе если задан topic_id — отправляем в этот топик форума
        reply_target = reply_to_msg_id if reply_to_msg_id else topic_id
        if reply_target:
            try:
                reply_target = int(reply_target)
            except ValueError:
                pass

        sent_msg = await client.send_message(
            c_id,
            text,
            reply_to=reply_target
        )

        me = await client.get_me()
        my_name = f"{getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}".strip() or "Вы"
        my_username = getattr(me, 'username', '') or ''
        my_id = str(me.id)

        # Аудит-лог
        await log_event(
            action_type="message_sent",
            actor=f"{my_name} (@{my_username})",
            status="success",
            details=f"Отправлен ответ в чат {chat_id}" + (f" (на сообщение {reply_to_msg_id})" if reply_to_msg_id else "") + f": {text[:100]}",
            chat_id=str(chat_id),
            extra={"message_id": sent_msg.id, "reply_to": reply_target, "topic_id": topic_id}
        )

        # Рассылка живого события в веб-панель
        await broadcast_event("new_message", {
            "chat_id": str(chat_id),
            "id": sent_msg.id,
            "text": text,
            "is_outgoing": True,
            "is_read": False,
            "sender_name": "Вы (Менеджер)",
            "sender_username": my_username,
            "sender_id": my_id,
            "sender_avatar_url": f"/api/avatar/{session}/{my_id}",
            "reply_to_msg_id": reply_to_msg_id,
            "topic_id": topic_id,
            "has_media": False,
            "date": datetime.now().strftime("%d.%m %H:%M:%S")
        })

        return {
            "status": "success",
            "message_id": sent_msg.id,
            "date": datetime.now().strftime("%d.%m %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в чат {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chats/mark_read")
async def api_mark_chat_read(payload: dict):
    """Отметка чата как прочитанного в Telegram"""
    chat_id = payload.get("chat_id")
    session = payload.get("session", "account_1")
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id обязателен")
    client = ACTIVE_CLIENTS.get(session)
    if not client and ACTIVE_CLIENTS:
        client = next(iter(ACTIVE_CLIENTS.values()))
    if not client:
        raise HTTPException(status_code=404, detail="Нет активных клиентов")
    try:
        try:
            c_id = int(chat_id)
        except ValueError:
            c_id = chat_id
        await client.send_read_acknowledge(c_id)
        await broadcast_event("chat_marked_read", {
            "chat_id": str(chat_id),
            "session": session
        })
        return {"status": "success", "chat_id": str(chat_id)}
    except Exception as e:
        logger.error(f"Ошибка отметки прочитанным {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chats/categories")
async def api_get_all_categories():
    """Возвращает список всех назначенных категорий и доступных ролей"""
    cats = await get_all_chat_categories()
    return {"categories": cats, "available_roles": CATEGORY_TITLES}

@app.get("/api/n8n/workflows")
async def api_get_n8n_workflows():
    """
    Возвращает реальный список рабочих процессов из локального n8n.
    Сначала пробует REST API (если задан N8N_API_KEY), затем напрямую из ~/.n8n/database.sqlite
    """
    workflows = []
    n8n_url = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678").split("/webhook")[0].rstrip("/")
    api_key = os.getenv("N8N_API_KEY", "").strip()

    # 1. Попытка через REST API n8n
    if api_key:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{n8n_url}/api/v1/workflows",
                    headers={"X-N8N-API-KEY": api_key},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_items = data.get("data", [])
                        for item in raw_items:
                            workflows.append({
                                "id": str(item.get("id")),
                                "name": item.get("name", "Без названия"),
                                "active": bool(item.get("active", False)),
                                "webhook_path": "",
                                "webhook_url": ""
                            })
                        return {"workflows": workflows, "source": "api"}
        except Exception as e:
            logger.warning(f"Ошибка запроса к n8n REST API: {e}")

    # 2. Прямое чтение из локальной SQLite базы данных n8n (~/.n8n/database.sqlite)
    sqlite_paths = [
        os.path.expanduser("~/.n8n/database.sqlite"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".n8n", "database.sqlite")
    ]
    for db_file in sqlite_paths:
        if os.path.exists(db_file):
            try:
                conn = sqlite3.connect(db_file)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                query = """
                    SELECT w.id, w.name, w.active, wh.webhookPath, wh.method
                    FROM workflow_entity w
                    LEFT JOIN webhook_entity wh ON w.id = wh.workflowId
                    WHERE w.isArchived = 0 OR w.isArchived IS NULL
                    ORDER BY w.active DESC, w.name ASC
                """
                cur.execute(query)
                seen_ids = set()
                for row in cur.fetchall():
                    w_id = str(row["id"])
                    wh_path = row["webhookPath"] or ""
                    wh_url = f"{n8n_url}/webhook/{wh_path}" if wh_path else ""
                    if w_id not in seen_ids:
                        seen_ids.add(w_id)
                        workflows.append({
                            "id": w_id,
                            "name": row["name"] or "Без названия",
                            "active": bool(row["active"]),
                            "webhook_path": wh_path,
                            "webhook_url": wh_url
                        })
                conn.close()
                return {"workflows": workflows, "source": "sqlite", "db_path": db_file}
            except Exception as e:
                logger.warning(f"Ошибка чтения базы n8n SQLite ({db_file}): {e}")

    return {"workflows": workflows, "source": "none", "message": "n8n база не найдена или пуста"}


