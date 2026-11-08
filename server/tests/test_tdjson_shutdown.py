"""TDLib bridge behaviour that does not need the native library."""
import asyncio
import json
import threading
from types import SimpleNamespace

from foxygram.telegram.tdjson import TdClient


def test_receive_thread_stops_quietly_when_the_event_loop_is_already_closed():
    """TDLib can deliver its last events after the loop has shut down."""
    loop = asyncio.new_event_loop()
    loop.close()
    reply = json.dumps({"@type": "ok"}).encode()

    client = TdClient.__new__(TdClient)
    client._loop = loop
    client._stop = threading.Event()
    client._native = SimpleNamespace(lib=SimpleNamespace(td_receive=lambda _timeout: reply))

    client._receive_loop()
