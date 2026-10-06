import os
import re
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import bson
from bson.objectid import ObjectId
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception as e:
    AsyncIOMotorClient = None
    logging.getLogger("mongodb").warning(f"AsyncIOMotorClient not available: {e}")

from config import MONGODB_URI, MONGODB_DB_NAME, DUPLICATE_DOCS_TO_DB

logger = logging.getLogger("mongodb")

# Стандартный 17-значный формат VIN (буквы A-Z кроме I, O, Q и цифры 0-9)
VIN_REGEX = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)

_mongo_client: Optional[Any] = None
_db = None

def extract_vin(text: str) -> str:
    """Извлекает 17-значный VIN номер автомобиля из любого текста/названия файла"""
    if not text:
        return ""
    # Очищаем спецсимволы разделители типа _ - . в названии файла
    clean_text = text.replace("_", " ").replace("-", " ")
    match = VIN_REGEX.search(clean_text)
    return match.group(0).upper() if match else ""

# Android has no /etc/resolv.conf, which dnspython needs to resolve mongodb+srv:// (Atlas) records.
FALLBACK_DNS_SERVERS = ["1.1.1.1", "8.8.8.8"]
_dns_configured = False


def _configure_dns_for_android():
    global _dns_configured
    if _dns_configured or os.path.exists("/etc/resolv.conf"):
        return
    _dns_configured = True
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = FALLBACK_DNS_SERVERS
        dns.resolver.default_resolver = resolver
        logger.info("[MongoDB] /etc/resolv.conf отсутствует, использую DNS %s", FALLBACK_DNS_SERVERS)
    except Exception as e:
        logger.warning(f"[MongoDB] Не удалось настроить DNS: {e}")


def get_db():
    global _mongo_client, _db
    if AsyncIOMotorClient is None or not MONGODB_URI:
        return None
    if _db is None:
        try:
            _configure_dns_for_android()
            _mongo_client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
            _db = _mongo_client[MONGODB_DB_NAME]
        except Exception as e:
            logger.warning(f"Не удалось инициализировать MongoDB клиент: {e}")
            _db = None
    return _db

async def init_db():
    """Инициализация подключения и создание оптимизированных индексов"""
    db = get_db()
    if db is None:
        logger.warning("[MongoDB] MONGODB_URI не задан или motor недоступен. Работа в автономном режиме.")
        return False

    try:
        # Быстрая проверка соединения с таймаутом 2.5с (не блокирует оффлайн-режим)
        import asyncio
        await asyncio.wait_for(db.command("ping"), timeout=2.5)
        logger.info(f"[+] [MongoDB] Успешное подключение к Atlas (БД: '{MONGODB_DB_NAME}')")

        # Создание индексов для аудит-логов
        await db.audit_logs.create_index([("timestamp", -1)])
        await db.audit_logs.create_index([("vin", 1)])
        await db.audit_logs.create_index([("action_type", 1)])
        await db.audit_logs.create_index([("actor", 1)])
        await db.audit_logs.create_index([("status", 1)])
        await db.audit_logs.create_index([("level", 1)])

        # Создание индексов для документов
        await db.documents.create_index([("created_at", -1)])
        await db.documents.create_index([("vin", 1)])
        await db.documents.create_index([("sender_id", 1)])
        await db.documents.create_index([("sender_phone", 1)])
        await db.documents.create_index([("filename", 1)])

        # Создание индексов для заметок и эскалаций
        await db.deal_notes.create_index([("created_at", -1)])
        await db.deal_notes.create_index([("chat_id", 1)])
        await db.deal_notes.create_index([("note_type", 1)])

        # Создание индексов для категорий чатов
        await db.chat_categories.create_index([("key", 1)], unique=True)
        await db.chat_categories.create_index([("chat_id", 1)])
        await db.chat_categories.create_index([("category", 1)])
        await db.chat_categories.create_index([("project_id", 1)])

        # Создание индексов для проектов
        await db.projects.create_index([("id", 1)], unique=True)
        await db.projects.create_index([("status", 1)])
        await db.projects.create_index([("created_at", -1)])

        await ensure_default_projects()
        await load_all_categories()

        logger.info("[+] [MongoDB] Индексы 'audit_logs', 'documents', 'deal_notes', 'chat_categories', 'projects' созданы.")
        return True
    except Exception as e:
        logger.exception(f"[!] [MongoDB] Ошибка подключения к базе данных: {e}")
        return False

async def log_event(
    action_type: str,
    actor: str,
    status: str = "success",
    details: str = "",
    vin: str = "",
    entity_type: str = "general",
    entity_id: str = "",
    level: str = "INFO",
    chat_id: str = "",
    extra: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> Optional[str]:
    """
    Записывает структурированное событие в коллекцию audit_logs.
    Поддерживает фильтрацию по VIN, дате, типу действия, статусу, автору.
    """
    db = get_db()
    if db is None:
        return None

    # Если VIN не передан явно, пробуем найти в details или entity_id
    if not vin and details:
        vin = extract_vin(details)
    if not vin and entity_id:
        vin = extract_vin(str(entity_id))

    extra_dict = dict(extra or {})
    if kwargs:
        extra_dict.update(kwargs)

    record = {
        "timestamp": datetime.utcnow(),
        "time_str": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "level": level.upper(),
        "action_type": action_type,
        "actor": actor or "system",
        "status": status,
        "details": details or "",
        "vin": vin.upper() if vin else "",
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else "",
        "chat_id": str(chat_id) if chat_id else "",
        "extra": extra_dict
    }

    try:
        res = await db.audit_logs.insert_one(record)
        return str(res.inserted_id)
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка записи лога: {e}")
        return None

async def save_document(
    metadata: Dict[str, Any],
    file_bytes: Optional[bytes] = None,
    vin: str = ""
) -> Optional[str]:
    """
    Сохраняет метаданные и бинарное содержимое документа в коллекцию documents.
    """
    db = get_db()
    if db is None:
        return None

    filename = metadata.get("filename", "unnamed.bin")
    caption = metadata.get("caption", "")

    # Определение VIN номера
    detected_vin = vin or extract_vin(filename) or extract_vin(caption)

    doc_record = {
        "created_at": datetime.utcnow(),
        "time_str": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "filename": filename,
        "mime_type": metadata.get("mime_type", "application/octet-stream"),
        "file_size": len(file_bytes) if file_bytes else 0,
        "vin": detected_vin.upper() if detected_vin else "",
        "sender_id": str(metadata.get("sender_id", "")),
        "sender_phone": str(metadata.get("sender_phone", "")),
        "sender_username": str(metadata.get("sender_username", "")),
        "first_name": str(metadata.get("first_name", "")),
        "last_name": str(metadata.get("last_name", "")),
        "chat_id": str(metadata.get("chat_id", "")),
        "message_id": metadata.get("message_id"),
        "caption": caption,
        "account_session": metadata.get("account_session", ""),
        "category": metadata.get("category", "none"),
        "category_title": metadata.get("category_title", "Без категории"),
        "project_id": metadata.get("project_id", ""),
        "project_name": metadata.get("project_name", ""),
        "chat_type": metadata.get("chat_type", "private"),
        "topic_id": str(metadata.get("topic_id", "")) if metadata.get("topic_id") else None,
        "n8n_status": metadata.get("n8n_status", "pending"),
        "rules_actions": metadata.get("rules_actions", []),
        "extra": metadata.get("extra", {})
    }

    # Дублируем бинарные данные файла в BSON Binary, если включено
    if DUPLICATE_DOCS_TO_DB and file_bytes:
        doc_record["file_bytes"] = bson.binary.Binary(file_bytes)
        doc_record["has_binary"] = True
    else:
        doc_record["has_binary"] = False

    try:
        res = await db.documents.insert_one(doc_record)
        doc_id = str(res.inserted_id)

        # Запись в аудит-лог
        await log_event(
            action_type="document_received",
            actor=f"{doc_record['first_name']} (@{doc_record['sender_username'] or doc_record['sender_id']})",
            status="success",
            details=f"Документ '{filename}' ({doc_record['file_size']} байт) сохранен в MongoDB",
            vin=doc_record["vin"],
            entity_type="document",
            entity_id=doc_id,
            extra={"filename": filename, "n8n_status": doc_record["n8n_status"]}
        )

        return doc_id
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка сохранения документа: {e}")
        return None

async def save_deal_note(
    chat_id: str,
    message_id: int,
    text: str,
    note_type: str = "note",  # "note" или "escalation"
    author: str = "Менеджер",
    vin: str = "",
    extra: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Сохраняет заметку менеджера к сделке или запрос на эскалацию
    """
    db = get_db()
    if db is None:
        return None

    detected_vin = vin or extract_vin(text)

    note_record = {
        "created_at": datetime.utcnow(),
        "time_str": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "chat_id": str(chat_id),
        "message_id": message_id,
        "text": text,
        "note_type": note_type,
        "author": author,
        "vin": detected_vin,
        "status": "pending" if note_type == "escalation" else "active",
        "extra": extra or {}
    }

    try:
        res = await db.deal_notes.insert_one(note_record)
        note_id = str(res.inserted_id)

        action = "escalation_created" if note_type == "escalation" else "note_created"
        await log_event(
            action_type=action,
            actor=author,
            status="escalated" if note_type == "escalation" else "success",
            details=f"[{'⚠️ ЭСКАЛАЦИЯ' if note_type == 'escalation' else '📝 ЗАМЕТКА'}] Чат {chat_id}: {text[:100]}",
            vin=detected_vin,
            entity_type="deal_note",
            entity_id=note_id
        )

        return note_id
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка сохранения заметки/эскалации: {e}")
        return None

async def get_audit_logs(
    vin: str = "",
    action_type: str = "",
    status: str = "",
    level: str = "",
    actor: str = "",
    search: str = "",
    start_date: str = "",
    end_date: str = "",
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Выборка аудит-логов с поддержкой сложной фильтрации
    """
    db = get_db()
    if db is None:
        return [], 0

    query: Dict[str, Any] = {}

    if vin:
        query["vin"] = {"$regex": vin.strip(), "$options": "i"}
    if action_type:
        query["action_type"] = action_type.strip()
    if status:
        query["status"] = status.strip()
    if level:
        query["level"] = level.strip().upper()
    if actor:
        query["actor"] = {"$regex": actor.strip(), "$options": "i"}
    if search:
        query["$or"] = [
            {"details": {"$regex": search.strip(), "$options": "i"}},
            {"entity_id": {"$regex": search.strip(), "$options": "i"}},
            {"actor": {"$regex": search.strip(), "$options": "i"}}
        ]

    # Фильтр по дате
    date_filter = {}
    if start_date:
        try:
            date_filter["$gte"] = datetime.fromisoformat(start_date)
        except Exception:
            pass
    if end_date:
        try:
            date_filter["$lte"] = datetime.fromisoformat(end_date)
        except Exception:
            pass
    if date_filter:
        query["timestamp"] = date_filter

    try:
        total = await db.audit_logs.count_documents(query)
        cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            if isinstance(doc.get("timestamp"), datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            items.append(doc)
        return items, total
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка запроса логов: {e}")
        return [], 0

async def get_documents(
    vin: str = "",
    sender: str = "",
    search: str = "",
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Выборка документов из базы (без бинарных данных для быстродействия)
    """
    db = get_db()
    if db is None:
        return [], 0

    query: Dict[str, Any] = {}
    if vin:
        query["vin"] = {"$regex": vin.strip(), "$options": "i"}
    if sender:
        query["$or"] = [
            {"sender_username": {"$regex": sender.strip(), "$options": "i"}},
            {"sender_phone": {"$regex": sender.strip(), "$options": "i"}},
            {"first_name": {"$regex": sender.strip(), "$options": "i"}}
        ]
    if search:
        query["$or"] = [
            {"filename": {"$regex": search.strip(), "$options": "i"}},
            {"caption": {"$regex": search.strip(), "$options": "i"}}
        ]

    try:
        total = await db.documents.count_documents(query)
        cursor = db.documents.find(query, {"file_bytes": 0}).sort("created_at", -1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            if isinstance(doc.get("created_at"), datetime):
                doc["created_at"] = doc["created_at"].isoformat()
            items.append(doc)
        return items, total
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка запроса документов: {e}")
        return [], 0

async def get_document_binary(doc_id: str) -> Optional[Tuple[bytes, str, str]]:
    """
    Возвращает (file_bytes, filename, mime_type) для скачивания файла из MongoDB
    """
    db = get_db()
    if db is None:
        return None

    try:
        doc = await db.documents.find_one({"_id": ObjectId(doc_id)})
        if not doc or "file_bytes" not in doc:
            return None
        return (bytes(doc["file_bytes"]), doc.get("filename", "download.bin"), doc.get("mime_type", "application/octet-stream"))
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка получения файла {doc_id}: {e}")
        return None

async def get_deal_notes(chat_id: str = "", note_type: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Выборка заметок к сделкам и эскалаций"""
    db = get_db()
    if db is None:
        return []

    query: Dict[str, Any] = {}
    if chat_id:
        query["chat_id"] = str(chat_id)
    if note_type:
        query["note_type"] = note_type

    try:
        cursor = db.deal_notes.find(query).sort("created_at", -1).limit(limit)
        items = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            if isinstance(doc.get("created_at"), datetime):
                doc["created_at"] = doc["created_at"].isoformat()
            items.append(doc)
        return items
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка запроса заметок: {e}")
        return []

# ----------------- Категоризация чатов и топиков -----------------

from pathlib import Path
from config import BASE_DIR
import json

PROJECTS_CACHE_FILE = BASE_DIR / "projects_cache.json"
CATEGORIES_CACHE_FILE = BASE_DIR / "categories_cache.json"

CATEGORY_CACHE: Dict[str, Any] = {}
PROJECTS_CACHE: List[Dict[str, Any]] = []

def _load_local_caches():
    global CATEGORY_CACHE, PROJECTS_CACHE
    p_file = PROJECTS_CACHE_FILE
    if not p_file.exists():
        p_file = Path(__file__).resolve().parent / "projects_cache.json"
    if p_file.exists():
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if loaded and isinstance(loaded, list):
                    PROJECTS_CACHE = loaded
                    logger.info(f"[Cache] Загружено {len(PROJECTS_CACHE)} проектов из локального кэша")
        except Exception as e:
            logger.warning(f"Ошибка чтения {p_file}: {e}")

    c_file = CATEGORIES_CACHE_FILE
    if not c_file.exists():
        c_file = Path(__file__).resolve().parent / "categories_cache.json"
    if c_file.exists():
        try:
            with open(c_file, "r", encoding="utf-8") as f:
                cats = json.load(f)
                if cats and isinstance(cats, list):
                    for item in cats:
                        key = item.get("key") or make_category_key(item.get("chat_id"), item.get("topic_id"))
                        CATEGORY_CACHE[key] = item
                    logger.info(f"[Cache] Загружено {len(CATEGORY_CACHE)} категорий чатов из локального кэша")
        except Exception as e:
            logger.warning(f"Ошибка чтения {c_file}: {e}")

def _save_projects_cache(projects_list: List[Dict[str, Any]]):
    try:
        target = BASE_DIR / "projects_cache.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(projects_list, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Ошибка сохранения кэша проектов: {e}")

def _save_categories_cache(categories_list: List[Dict[str, Any]]):
    try:
        target = BASE_DIR / "categories_cache.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(categories_list, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Ошибка сохранения кэша категорий: {e}")

CATEGORY_TITLES = {
    "client": "👤 Клиент",
    "broker": "💼 Брокер",
    "logist": "🚚 Логист",
    "customs": "🛃 Таможня",
    "internal_client": "🏢 Внутренний Клиент",
    "personal": "🔒 Личное",
    "trash": "🗑️ Мусор",
    "none": "⚪ Без категории"
}

def make_category_key(chat_id, topic_id=None) -> str:
    c = str(chat_id).strip()
    if topic_id:
        return f"{c}:{topic_id}"
    return c

async def set_chat_category(
    chat_id: str,
    category: str,
    topic_id: Optional[str] = None,
    title: str = "",
    assigned_by: str = "Менеджер",
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Назначает категорию чату или конкретному топику в форуме и сохраняет в MongoDB
    """
    db = get_db()
    key = make_category_key(chat_id, topic_id)
    cat = category.strip().lower() if category else "none"
    title_display = CATEGORY_TITLES.get(cat, cat)

    # Сохраняем или обновляем project_id
    existing = await get_chat_category(str(chat_id), str(topic_id) if topic_id else None) or {}
    current_proj_id = existing.get("project_id")
    current_proj_name = existing.get("project_name")

    if project_id is not None:
        if project_id and project_id != "none":
            p = await get_project(project_id)
            current_proj_id = project_id
            current_proj_name = p.get("name") if p else project_id
        else:
            current_proj_id = None
            current_proj_name = None

    doc = {
        "key": key,
        "chat_id": str(chat_id),
        "topic_id": str(topic_id) if topic_id else None,
        "category": cat,
        "category_title": title_display,
        "project_id": current_proj_id,
        "project_name": current_proj_name,
        "title": title or existing.get("title", ""),
        "assigned_at": datetime.utcnow(),
        "assigned_at_str": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "assigned_by": assigned_by
    }

    CATEGORY_CACHE[key] = doc

    if db is not None:
        try:
            await db.chat_categories.update_one(
                {"key": key},
                {"$set": doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"[MongoDB] Ошибка сохранения категории {key}: {e}")

    return doc

async def get_chat_category(chat_id: str, topic_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Получает категорию чата. Если передан topic_id, сначала ищет категорию топика,
    а если она не задана — наследует категорию родительского чата.
    """
    # 1. Проверяем топик в кэше
    if topic_id:
        topic_key = make_category_key(chat_id, topic_id)
        if topic_key in CATEGORY_CACHE:
            cached_topic = CATEGORY_CACHE[topic_key]
            if cached_topic:
                return cached_topic

    # 2. Проверяем чат в кэше
    chat_key = make_category_key(chat_id)
    if chat_key in CATEGORY_CACHE:
        return CATEGORY_CACHE[chat_key]

    db = get_db()
    if db is not None:
        try:
            if topic_id:
                topic_key = make_category_key(chat_id, topic_id)
                found = await db.chat_categories.find_one({"key": topic_key})
                if found:
                    found["id"] = str(found["_id"])
                    del found["_id"]
                    CATEGORY_CACHE[topic_key] = found
                    return found
                else:
                    CATEGORY_CACHE[topic_key] = None

            found = await db.chat_categories.find_one({"key": chat_key})
            if found:
                found["id"] = str(found["_id"])
                del found["_id"]
                CATEGORY_CACHE[chat_key] = found
                return found
            else:
                CATEGORY_CACHE[chat_key] = None
        except Exception as e:
            logger.error(f"[MongoDB] Ошибка получения категории: {e}")

    return None

CATEGORY_REFRESH_SEC = 300  # как часто перечитывать все категории из Atlas
_categories_loaded_at = 0.0


async def load_all_categories(force: bool = False) -> Dict[str, Any]:
    """Загружает категории из MongoDB в память (не чаще раза в CATEGORY_REFRESH_SEC) или из локального кэша"""
    global _categories_loaded_at
    if not CATEGORY_CACHE:
        _load_local_caches()

    db = get_db()
    if db is None:
        return CATEGORY_CACHE
    if not force and CATEGORY_CACHE and time.monotonic() - _categories_loaded_at < CATEGORY_REFRESH_SEC:
        return CATEGORY_CACHE

    try:
        cursor = db.chat_categories.find({})
        items_list = []
        fresh = {}
        async for item in cursor:
            item["id"] = str(item["_id"])
            del item["_id"]
            fresh[item["key"]] = item
            items_list.append(item)
        # Заменяем кэш целиком, чтобы удалённые в базе категории не оставались в памяти
        CATEGORY_CACHE.clear()
        CATEGORY_CACHE.update(fresh)
        _categories_loaded_at = time.monotonic()
        if items_list:
            _save_categories_cache(items_list)
    except Exception as e:
        logger.warning(f"[MongoDB] Ошибка загрузки всех категорий ({e}). Используем локальный кэш ({len(CATEGORY_CACHE)} записей).")

    return CATEGORY_CACHE

async def get_all_chat_categories() -> List[Dict[str, Any]]:
    """Возвращает список всех категоризированных чатов"""
    await load_all_categories(force=True)
    return [c for c in CATEGORY_CACHE.values() if c]

DEFAULT_PROJECT_TEMPLATES = {
    "auto": {
        "id": "proj_auto",
        "name": "🚗 Авто-логистика и ВЭД",
        "type": "auto",
        "customer": "Клиенты и авто-дилеры",
        "description": "Сделки с автомобилями, проверка VIN, логистика, таможенное оформление",
        "color": "#38bdf8",
        "status": "active",
        "categories": [
            {
                "id": "client",
                "name": "Клиенты",
                "color": "#38bdf8",
                "icon": "👤",
                "process_name": "Telegram Doc Pipeline (Vision AI -> Cloud -> amoCRM)",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "broker",
                "name": "Брокеры",
                "color": "#fbbf24",
                "icon": "💼",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "logist",
                "name": "Логисты",
                "color": "#4ade80",
                "icon": "🚚",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "customs",
                "name": "Таможня",
                "color": "#818cf8",
                "icon": "🛃",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "internal_client",
                "name": "Внутренний Клиент",
                "color": "#c084fc",
                "icon": "🏢",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "personal",
                "name": "Личное",
                "color": "#94a3b8",
                "icon": "🔒",
                "process_name": "",
                "action": "ignore",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "trash",
                "name": "Мусор",
                "color": "#f87171",
                "icon": "🗑️",
                "process_name": "",
                "action": "trash",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            }
        ]
    },
    "hr": {
        "id": "proj_hr",
        "name": "👥 HR Консалтинг и Рекрутинг",
        "type": "hr",
        "customer": "Наниматели и соискатели",
        "description": "Скрининг резюме, ведение вакансий, подбор специалистов и коммуникация с командой",
        "color": "#a855f7",
        "status": "active",
        "categories": [
            {
                "id": "candidate",
                "name": "Кандидаты (Резюме)",
                "color": "#38bdf8",
                "icon": "👨‍💼",
                "process_name": "",
                "action": "auto_reply",
                "webhook_url": "",
                "auto_reply_enabled": True,
                "auto_reply_text": "Здравствуйте! Ваше резюме принято в обработку, HR-специалист свяжется с вами."
            },
            {
                "id": "hr_client",
                "name": "Заказчики вакансий",
                "color": "#fbbf24",
                "icon": "🏢",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "recruiter",
                "name": "Рекрутеры / Сорсеры",
                "color": "#34d399",
                "icon": "👥",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "employee",
                "name": "Сотрудники на онбординге",
                "color": "#818cf8",
                "icon": "🤝",
                "process_name": "",
                "action": "webhook",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "personal",
                "name": "Личное",
                "color": "#94a3b8",
                "icon": "🔒",
                "process_name": "",
                "action": "ignore",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            },
            {
                "id": "trash",
                "name": "Мусор",
                "color": "#f87171",
                "icon": "🗑️",
                "process_name": "",
                "action": "trash",
                "webhook_url": "",
                "auto_reply_enabled": False,
                "auto_reply_text": ""
            }
        ]
    }
}

async def cleanup_fake_process_names():
    """Очищает устаревшие вымышленные заглушки процессов в MongoDB Atlas"""
    db = get_db()
    if db is None:
        return
    fake_stubs = {
        "auto_client_process", "auto_broker_process", "auto_logistics_process",
        "auto_customs_process", "internal_sync", "ignore", "auto_trash",
        "hr_resume_screening", "hr_client_request", "hr_recruiter_sync",
        "hr_onboarding", "candidate_intake", "client_process", "partner_process",
        "resume_parse", "doc_ocr_vin"
    }
    real_client_wf = "Telegram Doc Pipeline (Vision AI -> Cloud -> amoCRM)"
    try:
        cats = await db.chat_categories.find({"process_name": {"$in": list(fake_stubs)}}).to_list(1000)
        for doc in cats:
            c_id = doc.get("category_id") or doc.get("category")
            new_proc = real_client_wf if c_id == "client" else ""
            await db.chat_categories.update_one(
                {"_id": doc["_id"]},
                {"$set": {"process_name": new_proc}}
            )
            k = doc.get("key")
            if k and k in CATEGORY_CACHE:
                CATEGORY_CACHE[k]["process_name"] = new_proc

        projs = await db.projects.find().to_list(100)
        for p in projs:
            updated_cats = []
            changed = False
            for c in p.get("categories", []):
                p_name = c.get("process_name", "")
                if p_name in fake_stubs:
                    c["process_name"] = real_client_wf if c.get("id") == "client" else ""
                    changed = True
                updated_cats.append(c)
            if changed:
                await db.projects.update_one(
                    {"_id": p["_id"]},
                    {"$set": {"categories": updated_cats}}
                )
    except Exception as e:
        logger.warning(f"Ошибка очистки устаревших процессов: {e}")

async def ensure_default_projects():
    """Гарантирует наличие базовых проектов (Авто и HR) в MongoDB Atlas"""
    db = get_db()
    if db is None:
        return
    try:
        await cleanup_fake_process_names()
        for t_key, t_data in DEFAULT_PROJECT_TEMPLATES.items():
            existing = await db.projects.find_one({"id": t_data["id"]})
            if not existing:
                doc = dict(t_data)
                doc["created_at"] = datetime.utcnow()
                doc["created_at_str"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                await db.projects.insert_one(doc)
                logger.info(f"[+] [MongoDB] Создан базовый проект: '{t_data['name']}' (ID: {t_data['id']})")
            else:
                # Обновляем категории базовых шаблонов
                await db.projects.update_one(
                    {"id": t_data["id"]},
                    {"$set": {"categories": t_data["categories"], "type": t_data["type"]}}
                )
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка инициализации базовых проектов: {e}")

_UNSET = "__UNSET__"

async def set_chat_project_and_category(
    chat_id: str,
    project_id: Any = _UNSET,
    category_id: Any = _UNSET,
    topic_id: Optional[str] = None,
    title: str = "",
    assigned_by: str = "Менеджер"
) -> Dict[str, Any]:
    """
    Привязывает чат или топик к проекту и категории с подтягиванием процесса n8n
    """
    db = get_db()
    key = make_category_key(chat_id, topic_id)
    existing = await get_chat_category(str(chat_id), str(topic_id) if topic_id else None) or {}

    # Обработка project_id: если передан (включая None, "none", ""), сбрасываем или устанавливаем
    if project_id is not _UNSET:
        if project_id in (None, "", "none", "null"):
            p_id = None
        else:
            p_id = str(project_id).strip()
    else:
        p_id = existing.get("project_id")

    # Обработка category_id: если передан (включая None, "none", ""), сбрасываем или устанавливаем
    if category_id is not _UNSET:
        if category_id in (None, "", "none", "null"):
            c_id = "none"
        else:
            c_id = str(category_id).strip().lower()
    else:
        c_id = existing.get("category_id") or existing.get("category", "none")

    if not c_id:
        c_id = "none"

    proj_doc = await get_project(p_id) if p_id else None
    proj_name = proj_doc.get("name") if proj_doc else None
    proj_type = proj_doc.get("type", "general") if proj_doc else "general"
    proj_color = proj_doc.get("color", "#38bdf8") if proj_doc else None

    # Поиск категории в категориях проекта
    cat_def = None
    if proj_doc and proj_doc.get("categories"):
        for c in proj_doc["categories"]:
            if c["id"] == c_id:
                cat_def = c
                break

    if cat_def:
        cat_name = cat_def.get("name", c_id)
        cat_color = cat_def.get("color")
        cat_icon = cat_def.get("icon", "")
        process_name = cat_def.get("process_name")
        webhook_url = cat_def.get("webhook_url")
    else:
        cat_name = CATEGORY_TITLES.get(c_id, c_id)
        cat_color = None
        cat_icon = None
        process_name = None
        webhook_url = None

    doc = {
        "key": key,
        "chat_id": str(chat_id),
        "topic_id": str(topic_id) if topic_id else None,
        "project_id": p_id,
        "project_name": proj_name,
        "project_type": proj_type,
        "project_color": proj_color,
        "category_id": c_id if c_id != "none" else None,
        "category_name": cat_name,
        "category_color": cat_color,
        "category_icon": cat_icon,
        "process_name": process_name,
        "webhook_url": webhook_url,
        # Совместимость с предыдущими версиями
        "category": c_id,
        "category_title": cat_name,
        "title": title or existing.get("title", ""),
        "assigned_at": datetime.utcnow(),
        "assigned_at_str": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "assigned_by": assigned_by
    }

    CATEGORY_CACHE[key] = doc
    if db is not None:
        try:
            await db.chat_categories.update_one(
                {"key": key},
                {"$set": doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"[MongoDB] Ошибка привязки чата {key}: {e}")

    return doc

async def set_chat_project(
    chat_id: str,
    project_id: Any = _UNSET,
    topic_id: Optional[str] = None
) -> Dict[str, Any]:
    """Привязывает чат или топик к проекту (сохраняя категорию)"""
    existing = await get_chat_category(str(chat_id), str(topic_id) if topic_id else None) or {}
    c_id = existing.get("category_id") or existing.get("category", "none")
    return await set_chat_project_and_category(
        chat_id=chat_id,
        project_id=project_id,
        category_id=c_id,
        topic_id=topic_id,
        title=existing.get("title", "")
    )

async def create_project(
    name: str,
    project_type: str = "custom",
    customer: str = "",
    description: str = "",
    color: str = "#38bdf8",
    categories: Optional[List[Dict[str, Any]]] = None,
    template: Optional[str] = None
) -> Dict[str, Any]:
    db = get_db()
    proj_id = f"proj_{int(datetime.utcnow().timestamp())}_{os.urandom(3).hex()}"

    # Начальные категории
    cats = []
    if template and template in DEFAULT_PROJECT_TEMPLATES:
        tmpl = DEFAULT_PROJECT_TEMPLATES[template]
        cats = [dict(c) for c in tmpl.get("categories", [])]
        if not project_type or project_type == "custom":
            project_type = tmpl.get("type", "custom")
    elif categories:
        cats = categories
    else:
        cats = [
            {"id": "client", "name": "👤 Клиенты", "color": "#38bdf8", "icon": "👤", "process_name": "", "action": "webhook", "webhook_url": ""},
            {"id": "partner", "name": "🤝 Партнеры", "color": "#fbbf24", "icon": "🤝", "process_name": "", "action": "webhook", "webhook_url": ""},
            {"id": "personal", "name": "🔒 Личное", "color": "#94a3b8", "icon": "🔒", "process_name": "", "action": "ignore", "webhook_url": ""},
            {"id": "trash", "name": "🗑️ Мусор", "color": "#f87171", "icon": "🗑️", "process_name": "", "action": "trash", "webhook_url": ""}
        ]

    doc = {
        "id": proj_id,
        "name": name.strip(),
        "type": project_type or "custom",
        "customer": customer.strip(),
        "description": description.strip(),
        "color": color or "#38bdf8",
        "categories": cats,
        "status": "active",
        "created_at": datetime.utcnow(),
        "created_at_str": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

    if db is not None:
        try:
            await db.projects.insert_one(doc)
        except Exception as e:
            logger.error(f"[MongoDB] Ошибка создания проекта {name}: {e}")

    doc["_id"] = str(doc.get("_id", proj_id))
    return doc

async def get_projects(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Возвращает проекты с подсчетом привязанных чатов (из MongoDB или из локального кэша)"""
    global PROJECTS_CACHE
    if not PROJECTS_CACHE:
        _load_local_caches()

    db = get_db()
    if db is None:
        if status and status != "all":
            return [p for p in PROJECTS_CACHE if p.get("status") == status]
        return PROJECTS_CACHE

    try:
        query = {}
        if status and status != "all":
            query["status"] = status
        cursor = db.projects.find(query).sort("created_at", -1)
        items = []
        async for p in cursor:
            p["_id"] = str(p["_id"])
            p_id = p["id"]
            p["chats_count"] = await db.chat_categories.count_documents({"project_id": p_id})
            
            # Подсчет чатов для каждой категории проекта
            cats = p.get("categories", [])
            for c in cats:
                c["chats_count"] = await db.chat_categories.count_documents({"project_id": p_id, "category_id": c["id"]})
            items.append(p)

        def proj_order(item):
            pid = item.get("id")
            if pid == "proj_auto":
                return 0
            if pid == "proj_hr":
                return 1
            return 2
        items.sort(key=proj_order)

        if items:
            PROJECTS_CACHE = items
            _save_projects_cache(items)

        return items
    except Exception as e:
        logger.warning(f"[MongoDB] Ошибка загрузки проектов ({e}). Используем локальный кэш ({len(PROJECTS_CACHE)} проектов).")
        if status and status != "all":
            return [p for p in PROJECTS_CACHE if p.get("status") == status]
        return PROJECTS_CACHE

async def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db is None or not project_id:
        return None
    try:
        p = await db.projects.find_one({"id": project_id})
        if p:
            p["_id"] = str(p["_id"])
            p_id = p["id"]
            p["chats_count"] = await db.chat_categories.count_documents({"project_id": p_id})
            for c in p.get("categories", []):
                c["chats_count"] = await db.chat_categories.count_documents({"project_id": p_id, "category_id": c["id"]})
            return p
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка поиска проекта {project_id}: {e}")
    return None

async def update_project(project_id: str, updates: Dict[str, Any]) -> bool:
    db = get_db()
    if db is None or not project_id:
        return False
    try:
        clean_updates = {k: v for k, v in updates.items() if k not in ("_id", "id")}
        clean_updates["updated_at"] = datetime.utcnow()
        res = await db.projects.update_one({"id": project_id}, {"$set": clean_updates})
        if "name" in clean_updates:
            await db.chat_categories.update_many(
                {"project_id": project_id},
                {"$set": {"project_name": clean_updates["name"]}}
            )
        if "color" in clean_updates:
            await db.chat_categories.update_many(
                {"project_id": project_id},
                {"$set": {"project_color": clean_updates["color"]}}
            )
        return res.modified_count > 0
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка обновления проекта {project_id}: {e}")
        return False

async def delete_project(project_id: str) -> bool:
    db = get_db()
    if db is None or not project_id:
        return False
    try:
        res = await db.projects.delete_one({"id": project_id})
        await db.chat_categories.update_many(
            {"project_id": project_id},
            {"$set": {
                "project_id": None,
                "project_name": None,
                "project_color": None,
                "project_type": None
            }}
        )
        return res.deleted_count > 0
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка удаления проекта {project_id}: {e}")
        return False

async def add_project_category(project_id: str, category: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Добавляет новую категорию в проект"""
    db = get_db()
    if db is None or not project_id:
        return None
    cat_id = category.get("id") or f"cat_{int(datetime.utcnow().timestamp())}_{os.urandom(2).hex()}"
    clean_cat = {
        "id": cat_id.strip().lower(),
        "name": category.get("name", "Новая категория").strip(),
        "color": category.get("color", "#38bdf8"),
        "icon": category.get("icon", "📁"),
        "process_name": category.get("process_name", ""),
        "webhook_url": category.get("webhook_url", ""),
        "auto_reply_enabled": bool(category.get("auto_reply_enabled", False)),
        "auto_reply_text": category.get("auto_reply_text", ""),
        "chats_count": 0
    }
    try:
        await db.projects.update_one(
            {"id": project_id},
            {"$push": {"categories": clean_cat}}
        )
        return clean_cat
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка добавления категории в {project_id}: {e}")
        return None

async def update_project_category(project_id: str, category_id: str, updates: Dict[str, Any]) -> bool:
    """Обновляет параметры категории внутри проекта"""
    db = get_db()
    if db is None or not project_id or not category_id:
        return False
    try:
        set_fields = {}
        for k, v in updates.items():
            if k not in ("_id", "id"):
                set_fields[f"categories.$.{k}"] = v
        if not set_fields:
            return True
        res = await db.projects.update_one(
            {"id": project_id, "categories.id": category_id},
            {"$set": set_fields}
        )
        # Если изменились имя или цвет категории — синхронизируем денормализованные чаты
        chat_updates = {}
        if "name" in updates:
            chat_updates["category_name"] = updates["name"]
            chat_updates["category_title"] = updates["name"]
        if "color" in updates:
            chat_updates["category_color"] = updates["color"]
        if "icon" in updates:
            chat_updates["category_icon"] = updates["icon"]
        if "process_name" in updates:
            chat_updates["process_name"] = updates["process_name"]
        if "webhook_url" in updates:
            chat_updates["webhook_url"] = updates["webhook_url"]

        if chat_updates:
            await db.chat_categories.update_many(
                {"project_id": project_id, "category_id": category_id},
                {"$set": chat_updates}
            )
        return res.modified_count > 0
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка обновления категории {category_id} в {project_id}: {e}")
        return False

async def delete_project_category(project_id: str, category_id: str) -> bool:
    """Удаляет категорию из проекта и сбрасывает категорию у привязанных диалогов"""
    db = get_db()
    if db is None or not project_id or not category_id:
        return False
    try:
        res = await db.projects.update_one(
            {"id": project_id},
            {"$pull": {"categories": {"id": category_id}}}
        )
        await db.chat_categories.update_many(
            {"project_id": project_id, "category_id": category_id},
            {"$set": {
                "category_id": "none",
                "category_name": "Без категории",
                "category": "none",
                "category_title": "Без категории",
                "category_color": None,
                "category_icon": None,
                "process_name": None,
                "webhook_url": None
            }}
        )
        return res.modified_count > 0
    except Exception as e:
        logger.error(f"[MongoDB] Ошибка удаления категории {category_id} из {project_id}: {e}")
        return False


