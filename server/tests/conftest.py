from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from foxygram.config import load_config
from foxygram.service import Service
from foxygram.telegram.session import ChatInfo


class FakeClient:
    def __init__(self, on_update):
        self.on_update = on_update
        self.calls = []

    def start(self):
        pass

    async def close(self):
        pass

    def fire(self, query):
        self.calls.append(query)

    async def call(self, query, timeout=60.0):
        self.calls.append(query)
        return {"@type": "ok", "messages": []}


@pytest.fixture
def config(tmp_path: Path):
    cfg = load_config(tmp_path)
    return replace(cfg, telegram=replace(cfg.telegram, api_id=12345, api_hash="abc"))


@pytest.fixture
async def service(config):
    from foxygram.telegram.session import TelegramSession

    session = TelegramSession(config, client_factory=FakeClient)
    svc = Service(config, session=session)
    yield svc
    svc.stop.set()
    svc.db.close()


def add_chat(service, chat_id=100, title="Логистика", kind="group", ai=True):
    info = ChatInfo(chat_id=chat_id, title=title, kind=kind)
    service.session.chats[chat_id] = info
    service.on_chat_changed(info)
    if ai:
        service.db.execute("UPDATE chats SET ai_enabled = 1 WHERE chat_id = ?", (chat_id,))
    return info


async def settle():
    await asyncio.sleep(0)
    await asyncio.sleep(0)
