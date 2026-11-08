"""Exercises the real TDLib library; skipped where it has not been downloaded."""
import asyncio

import pytest

from foxygram.telegram.session import TelegramSession
from foxygram.telegram.tdjson import find_library


def tdlib_available() -> bool:
    try:
        find_library()
    except FileNotFoundError:
        return False
    return True


@pytest.mark.skipif(not tdlib_available(), reason="tdjson not downloaded")
async def test_session_reaches_the_login_step(config):
    session = TelegramSession(config)
    session.start()
    try:
        for _ in range(100):
            if session.auth.state == "need_login":
                break
            await asyncio.sleep(0.1)
        assert session.auth.state == "need_login"
    finally:
        await session.close()
