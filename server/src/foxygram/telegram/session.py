"""The server's own Telegram session: login, chat metadata, and the message stream."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .. import __version__
from ..config import Config
from . import messages as msg
from .store import TdStore, chat_list
from .tdjson import TdClient, TdError

log = logging.getLogger("telegram")

HISTORY_FILL_TRIES = 3
TOPIC_PAGE = 100
MAX_TOPIC_PAGES = 10
MUTE_FOREVER_SECONDS = 2_147_483_647
DOWNLOAD_TIMEOUT = 600.0
# Message changes the browser shows. Each one asks it to reload the newest page of that chat.
MESSAGE_UPDATES = {
    "updateNewMessage",
    "updateMessageContent",
    "updateMessageEdited",
    "updateMessageInteractionInfo",
    "updateMessageSendFailed",
    "updateChatReadOutbox",
}
# A topic was created, renamed, closed or read. The browser reloads that group's list of topics.
TOPIC_UPDATES = {"updateForumTopic", "updateForumTopicInfo"}


def topic_id(topic: dict[str, Any]) -> int:
    return int((topic.get("info") or {}).get("forum_topic_id") or 0)


@dataclass
class ChatInfo:
    chat_id: int
    title: str = ""
    kind: str = "private"


@dataclass
class AuthStatus:
    state: str = "starting"
    qr_link: str = ""
    code_hint: str = ""
    code_in_telegram: bool = False
    password_hint: str = ""
    error: str = ""
    connection: str = ""


class TelegramSession:
    """Stays offline and views nothing on its own, so your read state and phone alerts are untouched.
    Only the browser client marks messages read, when you open a chat in it, like any Telegram app would."""

    def __init__(self, config: Config, client_factory: Callable[..., TdClient] = TdClient):
        self.config = config
        self.client = client_factory(self._on_update)
        self.auth = AuthStatus()
        self.chats: dict[int, ChatInfo] = {}
        self.users: dict[int, str] = {}
        self.my_id = 0
        self.ready = asyncio.Event()
        self.on_message: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self.on_message_edited: Callable[[int, int, dict[str, Any]], Awaitable[None]] | None = None
        self.on_messages_deleted: Callable[[int, list[int]], Awaitable[None]] | None = None
        self.on_chat_changed: Callable[[ChatInfo], None] | None = None
        self.on_event: Callable[[dict[str, Any]], None] | None = None
        self.store = TdStore()
        self.started_at = time.time()

    def start(self) -> None:
        self.client.start()

    async def close(self) -> None:
        await self.client.close()

    def sender_name(self, sender_id: int, chat_id: int) -> str:
        if sender_id in self.users:
            return self.users[sender_id]
        if sender_id in self.chats:
            return self.chats[sender_id].title
        return self.chats[chat_id].title if chat_id in self.chats else ""

    async def login_qr(self) -> None:
        self.auth.error = ""
        await self._guard(self.client.call({"@type": "requestQrCodeAuthentication", "other_user_ids": []}))

    async def login_phone(self, phone: str) -> None:
        self.auth.error = ""
        await self._guard(self.client.call({"@type": "setAuthenticationPhoneNumber", "phone_number": phone}))

    async def login_code(self, code: str) -> None:
        self.auth.error = ""
        await self._guard(self.client.call({"@type": "checkAuthenticationCode", "code": code}))

    async def login_password(self, password: str) -> None:
        self.auth.error = ""
        await self._guard(self.client.call({"@type": "checkAuthenticationPassword", "password": password}))

    async def _guard(self, call: Awaitable[dict[str, Any]]) -> None:
        try:
            await call
        except TdError as error:
            self.auth.error = error.message

    async def load_all_chats(self) -> None:
        await self._load_lists(["main", "archive"] + [f"folder{f['id']}" for f in self.store.folders])

    async def _load_lists(self, keys: list[str]) -> None:
        for key in keys:
            while True:
                try:
                    await self.client.call({"@type": "loadChats", "chat_list": chat_list(key), "limit": 200})
                except TdError as error:
                    if error.code != 404:  # 404 means every chat has been loaded
                        log.warning("loadChats: %s", error)
                    break

    async def history(self, chat_id: int, limit: int) -> list[dict[str, Any]]:
        """Most recent messages, newest first."""
        collected: list[dict[str, Any]] = []
        from_id = 0
        while len(collected) < limit:
            page = await self.client.call({
                "@type": "getChatHistory",
                "chat_id": chat_id,
                "from_message_id": from_id,
                "offset": 0,
                "limit": min(100, limit - len(collected)),
                "only_local": False,
            })
            batch = page.get("messages") or []
            if not batch:
                break
            collected.extend(batch)
            from_id = batch[-1]["id"]
        return collected

    # --- Calls the browser client makes ---

    async def history_page(self, chat_id: int, from_message_id: int, offset: int, limit: int,
                           topic: int = 0) -> list[dict[str, Any]]:
        """One page of a chat's history, or of one topic of it, newest first.
        TDLib often answers a first call with only what it has cached."""
        if topic:
            query = {"@type": "getForumTopicHistory", "chat_id": chat_id, "forum_topic_id": topic,
                     "from_message_id": from_message_id, "offset": offset, "limit": limit}
        else:
            query = {"@type": "getChatHistory", "chat_id": chat_id, "from_message_id": from_message_id,
                     "offset": offset, "limit": limit, "only_local": False}
        messages: list[dict[str, Any]] = []
        for _ in range(HISTORY_FILL_TRIES):
            page = await self.client.call(query)
            messages = [m for m in page.get("messages") or [] if m]
            if len(messages) >= limit or offset < 0:
                break
        return messages

    async def messages(self, chat_id: int, message_ids: list[int]) -> list[dict[str, Any]]:
        if not message_ids:
            return []
        found = await self.client.call({"@type": "getMessages", "chat_id": chat_id, "message_ids": message_ids})
        return [m for m in found.get("messages") or [] if m]

    async def open_chat(self, chat_id: int) -> None:
        await self.client.call({"@type": "openChat", "chat_id": chat_id})

    async def close_chat(self, chat_id: int) -> None:
        await self.client.call({"@type": "closeChat", "chat_id": chat_id})

    async def view_messages(self, chat_id: int, message_ids: list[int], topic: int = 0) -> None:
        source = "messageSourceForumTopicHistory" if topic else "messageSourceChatHistory"
        await self.client.call({
            "@type": "viewMessages",
            "chat_id": chat_id,
            "message_ids": message_ids,
            "source": {"@type": source},
            "force_read": True,
        })

    async def forum_topics(self, chat_id: int) -> list[dict[str, Any]]:
        """Every topic of a group with topics, pinned first, then by latest activity, as the phone lists them."""
        found: dict[int, dict[str, Any]] = {}
        offset_date = offset_message = offset_topic = 0
        for _ in range(MAX_TOPIC_PAGES):
            page = await self.client.call({
                "@type": "getForumTopics",
                "chat_id": chat_id,
                "query": "",
                "offset_date": offset_date,
                "offset_message_id": offset_message,
                "offset_forum_topic_id": offset_topic,
                "limit": TOPIC_PAGE,
            })
            fresh = [t for t in page.get("topics") or [] if topic_id(t) not in found]
            found.update((topic_id(t), t) for t in fresh)
            offset_date = page.get("next_offset_date", 0)
            offset_message = page.get("next_offset_message_id", 0)
            offset_topic = page.get("next_offset_forum_topic_id", 0)
            if not fresh or not (offset_date or offset_message or offset_topic):
                break
        return sorted(found.values(), key=lambda t: (bool(t.get("is_pinned")), int(t.get("order") or 0)), reverse=True)

    async def forum_topic(self, chat_id: int, topic: int) -> dict[str, Any]:
        return await self.client.call({"@type": "getForumTopic", "chat_id": chat_id, "forum_topic_id": topic})

    async def mark_read(self, chat_id: int) -> None:
        chat = self.store.chats.get(chat_id) or {}
        if chat.get("is_marked_as_unread"):
            await self.client.call({"@type": "toggleChatIsMarkedAsUnread", "chat_id": chat_id, "is_marked_as_unread": False})
        last = (chat.get("last_message") or {}).get("id")
        if last:
            await self.open_chat(chat_id)
            try:
                await self.view_messages(chat_id, [last])
            finally:
                await self.close_chat(chat_id)

    async def mark_unread(self, chat_id: int) -> None:
        await self.client.call({"@type": "toggleChatIsMarkedAsUnread", "chat_id": chat_id, "is_marked_as_unread": True})

    async def set_pinned(self, chat_id: int, pinned: bool, key: str = "main") -> None:
        await self.client.call({"@type": "toggleChatIsPinned", "chat_list": chat_list(key), "chat_id": chat_id,
                                "is_pinned": pinned})

    async def set_muted(self, chat_id: int, muted: bool) -> None:
        settings = dict((self.store.chats.get(chat_id) or {}).get("notification_settings") or {})
        settings["@type"] = "chatNotificationSettings"
        settings["use_default_mute_for"] = False
        settings["mute_for"] = MUTE_FOREVER_SECONDS if muted else 0
        await self.client.call({"@type": "setChatNotificationSettings", "chat_id": chat_id, "notification_settings": settings})

    async def set_archived(self, chat_id: int, archived: bool) -> None:
        await self.client.call({"@type": "addChatToList", "chat_id": chat_id,
                                "chat_list": chat_list("archive" if archived else "main")})

    async def read_chat_list(self, key: str) -> None:
        await self.client.call({"@type": "readChatList", "chat_list": chat_list(key)})

    async def send_text(self, chat_id: int, text: str, reply_to: int = 0, topic: int = 0) -> dict[str, Any]:
        query: dict[str, Any] = {
            "@type": "sendMessage",
            "chat_id": chat_id,
            "input_message_content": {
                "@type": "inputMessageText",
                "text": {"@type": "formattedText", "text": text, "entities": []},
                "clear_draft": True,
            },
        }
        if topic:
            query["topic_id"] = {"@type": "messageTopicForum", "forum_topic_id": topic}
        if reply_to:
            query["reply_to"] = {"@type": "inputMessageReplyToMessage", "message_id": reply_to}
        return await self.client.call(query)

    async def search_chats(self, query: str, limit: int = 30) -> list[int]:
        local = await self.client.call({"@type": "searchChats", "query": query, "limit": limit})
        ids = list(local.get("chat_ids") or [])
        try:
            remote = await self.client.call({"@type": "searchChatsOnServer", "query": query, "limit": limit})
            ids += [i for i in remote.get("chat_ids") or [] if i not in ids]
        except TdError:
            pass
        return ids

    async def download(self, file_id: int) -> dict[str, Any]:
        """Waits until the whole file is on disk and returns TDLib's file object."""
        return await self.client.call({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 16,
            "offset": 0,
            "limit": 0,
            "synchronous": True,
        }, timeout=DOWNLOAD_TIMEOUT)

    def _emit(self, event: dict[str, Any]) -> None:
        if self.on_event:
            self.on_event(event)

    def _emit_for(self, update: dict[str, Any]) -> None:
        tag = update.get("@type", "")
        if tag in MESSAGE_UPDATES:
            chat_id = update.get("chat_id") or (update.get("message") or {}).get("chat_id")
            if chat_id:
                self._emit({"t": "messages", "chat_id": chat_id})
        elif tag == "updateMessageSendSucceeded":
            message = update.get("message") or {}
            self._emit({"t": "sent", "chat_id": message.get("chat_id"), "old_id": update.get("old_message_id"),
                        "new_id": message.get("id")})
        elif tag == "updateDeleteMessages" and not update.get("from_cache"):
            self._emit({"t": "deleted", "chat_id": update.get("chat_id"), "ids": update.get("message_ids") or []})
        elif tag in TOPIC_UPDATES:
            chat_id = update.get("chat_id") or (update.get("info") or {}).get("chat_id")
            if chat_id:
                self._emit({"t": "topics", "chat_id": chat_id})
        elif tag in ("updateConnectionState", "updateAuthorizationState"):
            self._emit({"t": "state"})

    async def _on_update(self, update: dict[str, Any]) -> None:
        if self.store.apply(update):
            self._emit({"t": "chats"})
        self._emit_for(update)
        if update.get("@type") == "updateChatFolders" and self.ready.is_set():
            asyncio.create_task(self._load_lists([f"folder{f['id']}" for f in self.store.folders]))
        match update.get("@type"):
            case "updateAuthorizationState":
                await self._on_auth(update["authorization_state"])
            case "updateConnectionState":
                self.auth.connection = update["state"]["@type"].removeprefix("connectionState")
            case "updateNewChat":
                chat = update["chat"]
                info = ChatInfo(
                    chat_id=chat["id"],
                    title=chat.get("title", ""),
                    kind=msg.chat_kind(chat.get("type", {})),
                )
                self.chats[info.chat_id] = info
                self._changed(info)
            case "updateChatTitle":
                info = self.chats.get(update["chat_id"])
                if info:
                    info.title = update["title"]
                    self._changed(info)
            case "updateUser":
                user = update["user"]
                self.users[user["id"]] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            case "updateOption":
                if update["name"] == "my_id":
                    self.my_id = int(update["value"].get("value", 0))
            case "updateNewMessage":
                if self.on_message:
                    await self.on_message(update["message"])
            case "updateMessageContent":
                if self.on_message_edited:
                    await self.on_message_edited(update["chat_id"], update["message_id"], update["new_content"])
            case "updateDeleteMessages":
                if update.get("is_permanent") and self.on_messages_deleted:
                    await self.on_messages_deleted(update["chat_id"], update["message_ids"])

    def _changed(self, info: ChatInfo) -> None:
        if self.on_chat_changed:
            self.on_chat_changed(info)

    async def _on_auth(self, state: dict[str, Any]) -> None:
        tag = state["@type"]
        self.auth.qr_link = ""
        match tag:
            case "authorizationStateWaitTdlibParameters":
                self.auth.state = "starting"
                await self.client.call({
                    "@type": "setTdlibParameters",
                    "use_test_dc": False,
                    "database_directory": str(self.config.tdlib_dir),
                    "files_directory": str(self.config.tdlib_dir),
                    "database_encryption_key": "",
                    # The browser client downloads photos and files; this lets TDLib find and clean them up.
                    "use_file_database": True,
                    "use_chat_info_database": True,
                    "use_message_database": True,
                    "use_secret_chats": False,
                    "api_id": self.config.telegram.api_id,
                    "api_hash": self.config.telegram.api_hash,
                    "system_language_code": "ru",
                    "device_model": "FoxyGram Server",
                    "system_version": "Windows",
                    "application_version": __version__,
                })
            case "authorizationStateWaitPhoneNumber":
                self.auth.state = "need_login"
            case "authorizationStateWaitOtherDeviceConfirmation":
                self.auth.state = "qr"
                self.auth.qr_link = state["link"]
            case "authorizationStateWaitCode":
                self.auth.state = "need_code"
                info = state.get("code_info", {})
                self.auth.code_hint = info.get("phone_number", "")
                self.auth.code_in_telegram = info.get("type", {}).get("@type") == "authenticationCodeTypeTelegramMessage"
            case "authorizationStateWaitPremiumPurchase":
                self.auth.state = "payment_required"
            case "authorizationStateWaitPassword":
                self.auth.state = "need_password"
                self.auth.password_hint = state.get("password_hint", "")
            case "authorizationStateReady":
                self.auth.state = "ready"
                self.ready.set()
                asyncio.create_task(self.load_all_chats())
            case "authorizationStateClosed" | "authorizationStateClosing" | "authorizationStateLoggingOut":
                self.auth.state = "closed"
                self.ready.clear()
            case _:
                log.warning("unsupported login step: %s", tag)
                self.auth.state = "unsupported"
                self.auth.error = tag
