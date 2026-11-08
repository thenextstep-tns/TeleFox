"""Minimal asyncio bridge to TDLib's JSON interface."""
from __future__ import annotations

import asyncio
import ctypes
import itertools
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger("tdlib")

UpdateHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class TdError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def find_library() -> Path:
    name = "tdjson.dll" if os.name == "nt" else "libtdjson.so"
    roots = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).parent, Path(__file__).parents[3] / "vendor"]
    if os.environ.get("FOXYGRAM_TDJSON"):
        return Path(os.environ["FOXYGRAM_TDJSON"])
    for root in roots:
        candidate = root / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"{name} not found in {[str(r) for r in roots]}")


class _Native:
    def __init__(self, path: Path):
        lib = ctypes.CDLL(str(path))
        lib.td_create_client_id.restype = ctypes.c_int
        lib.td_send.argtypes = [ctypes.c_int, ctypes.c_char_p]
        lib.td_receive.argtypes = [ctypes.c_double]
        lib.td_receive.restype = ctypes.c_char_p
        lib.td_execute.argtypes = [ctypes.c_char_p]
        lib.td_execute.restype = ctypes.c_char_p
        self.lib = lib

    def execute(self, query: dict[str, Any]) -> dict[str, Any] | None:
        raw = self.lib.td_execute(json.dumps(query).encode())
        return json.loads(raw) if raw else None


class TdClient:
    """One TDLib instance. Replies resolve futures; everything else goes to on_update, in order."""

    def __init__(self, on_update: UpdateHandler, library: Path | None = None):
        self._native = _Native(library or find_library())
        self._native.execute({"@type": "setLogVerbosityLevel", "new_verbosity_level": 1})
        self._on_update = on_update
        self._client_id = self._native.lib.td_create_client_id()
        self._ids = itertools.count(1)
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._receive_loop, name="tdlib-receive", daemon=True)
        self._dispatcher: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._thread.start()
        self._dispatcher = asyncio.create_task(self._dispatch())
        # TDLib only starts once it receives a first request.
        self.fire({"@type": "getOption", "name": "version"})

    def fire(self, query: dict[str, Any]) -> None:
        self._native.lib.td_send(self._client_id, json.dumps(query, ensure_ascii=False).encode())

    async def call(self, query: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        extra = str(next(self._ids))
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[extra] = future
        self.fire({**query, "@extra": extra})
        try:
            result = await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(extra, None)
        if result.get("@type") == "error":
            raise TdError(int(result.get("code", 0)), str(result.get("message", "")))
        return result

    async def close(self) -> None:
        self.fire({"@type": "close"})
        self._stop.set()
        await self._queue.put(None)
        if self._dispatcher:
            await self._dispatcher

    def _receive_loop(self) -> None:
        receive = self._native.lib.td_receive
        while not self._stop.is_set():
            raw = receive(1.0)
            if raw and self._loop:
                self._loop.call_soon_threadsafe(self._route, json.loads(raw))

    def _route(self, event: dict[str, Any]) -> None:
        """Replies skip the queue: an update handler may be awaiting one, and it holds the queue."""
        extra = event.pop("@extra", None)
        future = self._pending.get(extra) if extra is not None else None
        if future is not None:
            if not future.done():
                future.set_result(event)
            return
        self._queue.put_nowait(event)

    async def _dispatch(self) -> None:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            try:
                outcome = self._on_update(event)
                if asyncio.iscoroutine(outcome):
                    await outcome
            except Exception:
                log.exception("update handler failed for %s", event.get("@type"))
