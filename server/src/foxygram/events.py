"""Pushes Telegram changes to open browser tabs. A burst of updates becomes one event per chat."""
from __future__ import annotations

import asyncio
import itertools
from typing import Any

QUEUE_SIZE = 500
# Events that stand for "reload this"; repeats inside one flush window carry no extra information.
MERGED = {"chats", "messages", "state", "topics"}


class EventHub:
    def __init__(self, delay: float = 0.25):
        self.delay = delay
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._pending: dict[str, dict[str, Any]] = {}
        self._scheduled = False
        self._ids = itertools.count()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    @property
    def listeners(self) -> int:
        return len(self._subscribers)

    def publish(self, event: dict[str, Any]) -> None:
        if not self._subscribers:
            return
        kind = event.get("t", "")
        key = f"{kind}:{event.get('chat_id', '')}" if kind in MERGED else f"{kind}:{next(self._ids)}"
        self._pending.pop(key, None)
        self._pending[key] = event
        if not self._scheduled:
            self._scheduled = True
            asyncio.get_running_loop().call_later(self.delay, self._flush)

    def _flush(self) -> None:
        self._scheduled = False
        events, self._pending = list(self._pending.values()), {}
        for queue in list(self._subscribers):
            for event in events:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # A tab that stopped reading reloads everything when it reconnects.
                    break
