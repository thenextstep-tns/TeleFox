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
from .tdjson import TdClient, TdError

log = logging.getLogger("telegram")

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
    password_hint: str = ""
    error: str = ""
    connection: str = ""


class TelegramSession:
    """Stays offline and never views messages, so your read state and phone alerts are untouched."""

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
        for chat_list in ({"@type": "chatListMain"}, {"@type": "chatListArchive"}):
            while True:
                try:
                    await self.client.call({"@type": "loadChats", "chat_list": chat_list, "limit": 200})
                except TdError as error:
                    if error.code == 404:  # every chat has been loaded
                        break
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

    async def _on_update(self, update: dict[str, Any]) -> None:
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
                    "use_file_database": False,
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
                self.auth.code_hint = state.get("code_info", {}).get("phone_number", "")
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
