import os
import sys
import json
import shutil
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, SESSIONS_DIR

logger = logging.getLogger("TeleFoxService")

SETTINGS_FILE = BASE_DIR / "notification_settings.json"

DEFAULT_SETTINGS = {
    "enabled": True,
    "projects": "all",  # "all" or list of project IDs e.g. ["proj_auto", "proj_hr"]
    "categories": "all",  # "all" or list of category IDs
    "exclude_trash": True,
    "exclude_personal": True,
    "chat_types": "private_and_topics",  # "private", "private_and_topics", "all"
    "sound": True,
    "vibrate": True,
    "vibration_pattern": [200, 100, 200],
    "quiet_hours_enabled": False,
    "quiet_hours_start": "23:00",
    "quiet_hours_end": "08:00"
}

def load_notification_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception as e:
            logger.warning(f"Ошибка загрузки настроек уведомлений: {e}")
    return DEFAULT_SETTINGS.copy()

def save_notification_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def is_quiet_hours(settings: dict) -> bool:
    if not settings.get("quiet_hours_enabled"):
        return False
    try:
        now = datetime.now().time()
        start_parts = [int(p) for p in settings.get("quiet_hours_start", "23:00").split(":")]
        end_parts = [int(p) for p in settings.get("quiet_hours_end", "08:00").split(":")]
        start_time = datetime.now().replace(hour=start_parts[0], minute=start_parts[1], second=0).time()
        end_time = datetime.now().replace(hour=end_parts[0], minute=end_parts[1], second=0).time()

        if start_time < end_time:
            return start_time <= now <= end_time
        else:
            return now >= start_time or now <= end_time
    except Exception:
        return False

def should_notify_for_message(msg_data: dict, settings: dict) -> bool:
    """Проверка правил фильтрации для входящего сообщения"""
    if not settings.get("enabled", True):
        return False

    if is_quiet_hours(settings):
        return False

    project_id = msg_data.get("project_id") or "unassigned"
    category_id = msg_data.get("category_id") or "none"
    is_private = msg_data.get("is_private", True)
    is_forum = msg_data.get("is_forum", False)

    # Исключение личного и мусора
    if settings.get("exclude_trash") and category_id == "trash":
        return False
    if settings.get("exclude_personal") and category_id == "personal":
        return False

    # Фильтр типов чата
    chat_type_rule = settings.get("chat_types", "private_and_topics")
    if chat_type_rule == "private" and not is_private:
        return False
    elif chat_type_rule == "private_and_topics" and not (is_private or is_forum):
        return False

    # Фильтр по проектам
    allowed_projects = settings.get("projects", "all")
    if allowed_projects != "all" and isinstance(allowed_projects, list):
        if project_id not in allowed_projects:
            return False

    # Фильтр по категориям
    allowed_categories = settings.get("categories", "all")
    if allowed_categories != "all" and isinstance(allowed_categories, list):
        if category_id not in allowed_categories:
            return False

    return True

def _native_notifier():
    """Java-класс com.telefox.app.Notifier (доступен только внутри Android-приложения)."""
    try:
        from java import jclass
        return jclass("com.telefox.app.Notifier")
    except Exception:
        return None


def dispatch_android_notification(title: str, text: str, chat_id: str, settings: dict):
    """Системное уведомление Android о новом сообщении (no-op вне приложения)."""
    notifier = _native_notifier()
    if notifier is None:
        return
    try:
        notifier.notifyMessage(
            title,
            text[:200],
            str(chat_id),
            bool(settings.get("sound", True)),
            bool(settings.get("vibrate", True)),
        )
    except Exception as e:
        logger.warning(f"Не удалось показать уведомление: {e}")
