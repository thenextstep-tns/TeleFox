"""Connects the Telegram stream to storage and analysis."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from .analysis import IncomingRow, store_message, worker
from .config import Config
from .db import Database
from .engine import ClaudeEngine
from .events import EventHub
from .telegram import messages as msg
from .telegram.session import ChatInfo, TelegramSession
from .tunnel import Tunnel

log = logging.getLogger("service")

BACKFILL_MESSAGES = 200


def pairing_uri(config: Config, url: str) -> str:
    """Everything the phone needs, so the public APK can ship without any credentials."""
    body = json.dumps({
        "u": url,
        "t": config.secrets.api_token,
        "i": config.telegram.api_id,
        "h": config.telegram.api_hash,
    }, separators=(",", ":"))
    return "foxygram://pair?d=" + base64.urlsafe_b64encode(body.encode()).rstrip(b"=").decode()


class Service:
    def __init__(self, config: Config, session: TelegramSession | None = None, engine: ClaudeEngine | None = None):
        self.config = config
        self.db = Database(config.db_path)
        self.session = session or TelegramSession(config)
        self.engine = engine or ClaudeEngine(config.claude, self.db, config.sandbox_dir)
        self.tunnel = Tunnel(config.tunnel, config.server, config.cloudflared_config)
        self.stop = asyncio.Event()
        self.phone_seen_at = 0
        self._tasks: list[asyncio.Task[Any]] = []
        self.session.on_message = self.on_message
        self.session.on_message_edited = self.on_edited
        self.session.on_messages_deleted = self.on_deleted
        self.session.on_chat_changed = self.on_chat_changed
        self.events = EventHub()
        self.session.on_event = self.events.publish

    def start(self) -> None:
        self.session.start()
        self._tasks.append(asyncio.create_task(worker(
            self.db, self.engine, self.config.bursts, self.config.cases, self.stop)))
        self._tasks.append(asyncio.create_task(self.tunnel.run(self.stop)))

    async def close(self) -> None:
        self.stop.set()
        self.tunnel.stop()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.session.close()
        self.db.close()

    def on_chat_changed(self, info: ChatInfo) -> None:
        self.db.execute(
            "INSERT INTO chats(chat_id, title, kind) VALUES(?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, kind = excluded.kind",
            (info.chat_id, info.title, info.kind),
        )

    def _row(self, parsed: msg.Parsed) -> IncomingRow:
        return IncomingRow(
            chat_id=parsed.chat_id,
            message_id=parsed.message_id,
            date=parsed.date,
            sender_id=parsed.sender_id,
            sender_name=self.session.sender_name(parsed.sender_id, parsed.chat_id),
            outgoing=parsed.outgoing,
            kind=parsed.kind,
            text=parsed.text,
            reply_to=parsed.reply_to,
        )

    async def on_message(self, message: dict[str, Any]) -> None:
        parsed = msg.parse(message)
        if parsed.pending or parsed.kind == "service":
            return
        # Anything from a chat you did not select is dropped here, unread and unstored.
        if self.db.scalar("SELECT ai_enabled FROM chats WHERE chat_id = ?", (parsed.chat_id,)):
            store_message(self.db, self._row(parsed))

    async def on_edited(self, chat_id: int, message_id: int, content: dict[str, Any]) -> None:
        _, text = msg.content_of(content)
        self.db.execute("UPDATE messages SET text = ? WHERE chat_id = ? AND message_id = ?", (text, chat_id, message_id))

    async def on_deleted(self, chat_id: int, message_ids: list[int]) -> None:
        for message_id in message_ids:
            self.db.execute("DELETE FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))

    def set_chat_ai(self, chat_id: int, enabled: bool) -> None:
        was_enabled = self.db.scalar("SELECT ai_enabled FROM chats WHERE chat_id = ?", (chat_id,))
        self.db.execute("UPDATE chats SET ai_enabled = ? WHERE chat_id = ?", (int(enabled), chat_id))
        if enabled and not was_enabled:
            self._tasks.append(asyncio.create_task(self._backfill(chat_id)))

    async def _backfill(self, chat_id: int) -> None:
        """Recent history gives Claude and search some context, without spending any quota on it."""
        try:
            for message in await self.session.history(chat_id, BACKFILL_MESSAGES):
                parsed = msg.parse(message)
                if parsed.kind != "service" and not parsed.pending:
                    store_message(self.db, self._row(parsed), context_only=True)
        except Exception:
            log.exception("backfill failed for chat %s", chat_id)
