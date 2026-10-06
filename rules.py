import os
import copy
import json
import logging
import aiohttp
from pathlib import Path

import config

logger = logging.getLogger("rules")

WEBHOOK_TIMEOUT_SEC = 10


DEFAULT_RULES = {
    "chat_scope": {
        "mode": "all_private",
        "allowed_chats": [],
        "ignored_chats": []
    },
    "auto_reply": {
        "enabled": False,
        "mode": "all_docs",
        "keywords": ["документ", "паспорт", "снилс", "инн", "договор", "счет", "чек", "выписка", "doc", "scan"],
        "text": "Здравствуйте, {first_name}! Ваш документ '{filename}' успешно получен и передан в систему обработки."
    },
    "forward_to_chat": {
        "enabled": False,
        "target_chat": "",
        "notification_text": "📥 Новый документ от клиента {first_name} (@{username}, {sender_phone}): '{filename}'"
    },
    "alert_webhook": {
        "enabled": False,
        "webhook_url": "",
        "secret_token": ""
    },
    "filters": {
        "allowed_extensions": ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"],
        "ignore_bot_senders": True
    }
}

def _rules_file() -> Path:
    # config.BASE_DIR может смениться в reload_config(), поэтому читаем его каждый раз
    return config.BASE_DIR / "rules.json"

def load_rules() -> dict:
    path = _rules_file()
    if not path.exists():
        return copy.deepcopy(DEFAULT_RULES)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки {path}: {e}")
        return copy.deepcopy(DEFAULT_RULES)
    # Добавляем отсутствующие секции значениями по умолчанию
    for key, default in DEFAULT_RULES.items():
        data.setdefault(key, copy.deepcopy(default))
    return data

def save_rules(rules_data: dict):
    path = _rules_file()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения {path}: {e}")

def passes_filters(filename: str, sender_is_bot: bool, rules: dict) -> tuple:
    """Проверяет раздел `filters` (расширения файлов, боты). Возвращает (ok, reason)."""
    filters = rules.get("filters", {})
    if filters.get("ignore_bot_senders") and sender_is_bot:
        return False, "отправитель — бот"
    allowed_ext = [e.lower().lstrip(".") for e in filters.get("allowed_extensions", [])]
    if allowed_ext and filename:
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        # Фото без расширения в имени приходят как photo_<id>.jpg, поэтому пустое расширение пропускаем
        if ext and ext not in allowed_ext:
            return False, f"расширение .{ext} не разрешено"
    return True, ""

def clean_identifier(val) -> str:
    if not val:
        return ""
    s = str(val).strip().lower()
    if s.startswith("@"):
        s = s[1:]
    return s

def is_chat_allowed(chat_id, username: str, rules: dict, is_private: bool = True) -> tuple:
    """
    Проверяет, разрешена ли обработка данного чата согласно правилам.
    Возвращает (is_allowed: bool, reason: str)
    """
    scope = rules.get("chat_scope", {})
    mode = scope.get("mode", "all_private")
    allowed = [clean_identifier(x) for x in scope.get("allowed_chats", [])]
    ignored = [clean_identifier(x) for x in scope.get("ignored_chats", [])]

    c_id = clean_identifier(chat_id)
    u_name = clean_identifier(username)

    # 1. Проверка на черный список
    if (c_id and c_id in ignored) or (u_name and u_name in ignored):
        return False, f"Чат {chat_id} (@{username}) находится в списке исключений (черный список)"

    # 2. Если чат явно добавлен в белый список (или категоризирован) - всегда разрешаем
    if (c_id and c_id in allowed) or (u_name and u_name in allowed):
        return True, "Чат в белом списке"

    # 3. Режим белого списка
    if mode == "whitelist_only":
        return False, f"Чат {chat_id} (@{username}) не входит в список разрешенных чатов (Whitelist)"

    # 4. Режим всех личных диалогов (all_private)
    if mode == "all_private":
        if is_private:
            return True, "Разрешено (режим всех личных диалогов)"
        return False, f"Группа {chat_id} не добавлена в белый список (включен режим 'только личные')"

    # 5. Режим всех чатов (all_chats)
    return True, "Разрешено (режим всех чатов)"

def format_template(template: str, context: dict) -> str:
    try:
        safe_ctx = {k: ("" if v is None else str(v)) for k, v in context.items()}
        return template.format(**safe_ctx)
    except KeyError as e:
        logger.warning(f"Неизвестный ключ в шаблоне: {e}")
        return template
    except Exception as e:
        logger.error(f"Ошибка форматирования шаблона: {e}")
        return template

async def apply_business_rules(client, event, metadata: dict, filename: str) -> dict:
    """
    Применяет настроенные бизнес-правила при получении документа
    """
    rules = load_rules()
    actions_taken = []

    context = {
        "first_name": metadata.get("first_name") or "Клиент",
        "last_name": metadata.get("last_name") or "",
        "username": metadata.get("sender_username") or "без_username",
        "sender_phone": metadata.get("sender_phone") or "номер скрыт",
        "sender_id": metadata.get("sender_id") or "",
        "chat_id": metadata.get("chat_id") or "",
        "filename": filename,
        "caption": metadata.get("caption") or "",
        "account_session": metadata.get("account_session") or ""
    }

    # 1. Авто-ответ клиенту в Telegram
    auto_reply = rules.get("auto_reply", {})
    if auto_reply.get("enabled") and auto_reply.get("text"):
        mode = auto_reply.get("mode", "all_docs")
        should_reply = True
        skip_reason = ""

        if mode == "whitelist_only":
            allowed_chats = [clean_identifier(x) for x in rules.get("chat_scope", {}).get("allowed_chats", [])]
            cid = clean_identifier(event.chat_id)
            un = clean_identifier(metadata.get("sender_username"))
            if not ((cid and cid in allowed_chats) or (un and un in allowed_chats)):
                should_reply = False
                skip_reason = "чат не в белом списке для авто-ответа"

        elif mode == "keywords_only":
            keywords = auto_reply.get("keywords", [])
            text_to_search = f"{filename} {context['caption']}".lower()
            match = any(kw.strip().lower() in text_to_search for kw in keywords if kw.strip())
            if not match:
                should_reply = False
                skip_reason = "не найдены ключевые слова документа в названии или подписи"

        if should_reply:
            reply_text = format_template(auto_reply.get("text"), context)
            try:
                await client.send_message(event.chat_id, reply_text, reply_to=event.id)
                logger.info(f"[Бизнес-правило] Отправлен авто-ответ в чат {event.chat_id}: {reply_text[:60]}...")
                actions_taken.append({"type": "auto_reply", "status": "success", "text": reply_text})
            except Exception as e:
                logger.error(f"[Бизнес-правило] Ошибка отправки авто-ответа: {e}")
                actions_taken.append({"type": "auto_reply", "status": "error", "error": str(e)})
        else:
            logger.info(f"[Бизнес-правило] Авто-ответ пропущен ({skip_reason})")
            actions_taken.append({"type": "auto_reply", "status": "skipped", "reason": skip_reason})

    # 2. Пересылка / уведомление в рабочий чат (менеджеру / в группу)
    fwd = rules.get("forward_to_chat", {})
    if fwd.get("enabled") and fwd.get("target_chat"):
        target = fwd.get("target_chat").strip()
        fwd_text = format_template(fwd.get("notification_text", ""), context)
        try:
            try:
                target_entity = int(target)
            except ValueError:
                target_entity = target

            if fwd_text:
                await client.send_message(target_entity, fwd_text)
            await client.forward_messages(target_entity, event.message)
            logger.info(f"[Бизнес-правило] Документ успешно переслан в чат '{target}'")
            actions_taken.append({"type": "forward_to_chat", "status": "success", "target": target})
        except Exception as e:
            logger.error(f"[Бизнес-правило] Ошибка пересылки в чат '{target}': {e}")
            actions_taken.append({"type": "forward_to_chat", "status": "error", "error": str(e)})

    # 3. Внешний Webhook-алерт
    webhook_cfg = rules.get("alert_webhook", {})
    if webhook_cfg.get("enabled") and webhook_cfg.get("webhook_url"):
        url = webhook_cfg.get("webhook_url")
        payload = {
            "event": "document_received",
            "context": context,
            "metadata": metadata
        }
        headers = {"Content-Type": "application/json"}
        if webhook_cfg.get("secret_token"):
            headers["X-Alert-Secret"] = webhook_cfg.get("secret_token")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT_SEC)) as resp:
                    logger.info(f"[Бизнес-правило] Алерт отправлен на Webhook: {url} (HTTP {resp.status})")
                    actions_taken.append({"type": "alert_webhook", "status": "success", "http_status": resp.status})
        except Exception as e:
            logger.error(f"[Бизнес-правило] Ошибка отправки Webhook-алерта на {url}: {e}")
            actions_taken.append({"type": "alert_webhook", "status": "error", "error": str(e)})

    return {"actions": actions_taken}
