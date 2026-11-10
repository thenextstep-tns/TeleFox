"""Talks to Brain, the owner's agent system on this PC, about which of its jobs get a chat.

Only the server calls Brain. The phone and the browser call the server, so Brain's token never leaves this PC.
The token is read from Brain's .env on every call, so a new token works without restarting FoxyGram.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import BrainConfig, read_env_file

TIMEOUT_SECONDS = 5
TOKEN_KEY = "BRAIN_TOKEN"


# Brain keeps Telegram's own message ids. TDLib's id for a message on Telegram's servers is that id shifted left by 20.
TDLIB_SHIFT = 20


def to_tdlib(message_id: int) -> int:
    return int(message_id) << TDLIB_SHIFT


class BrainError(Exception):
    """Something the person can act on. status is what the server answers its own caller with."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


NOT_RUNNING = "Brain isn't running on this computer. Start Brain and try again."
NO_TOKEN = ("Brain's token wasn't found. FoxyGram looks for BRAIN_TOKEN in {path}; "
            "you can also put it in [brain] token in the server's config.toml.")
BAD_TOKEN = "Brain refused the token. Check BRAIN_TOKEN in Brain's .env or in the FoxyGram server's config.toml."
SLOW = "Brain didn't answer in time. Try again."
# Brain is on this PC, so a system proxy must never be in the way.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Brain:
    def __init__(self, config: BrainConfig):
        self.config = config

    def token(self) -> str:
        if self.config.token.strip():
            return self.config.token.strip()
        path = self.config.env_path
        try:
            return read_env_file(path).get(TOKEN_KEY, "") if path.exists() else ""
        except (OSError, UnicodeDecodeError):
            return ""

    async def chat(self, chat_id: int) -> dict[str, Any]:
        """The jobs Brain has, and which of them get this chat."""
        query = urllib.parse.urlencode({"chatId": str(chat_id)})
        return await self._call("GET", f"/chats/api/chat?{query}")

    async def assign(self, chat_id: int, job_id: str, on: bool) -> dict[str, Any]:
        return await self._call("POST", "/chats/api/assign", {"chatId": str(chat_id), "jobId": job_id, "on": on})

    async def sending(self, chat_id: int, on: bool) -> dict[str, Any]:
        """Sending off: Brain keeps reading the chat and shows what it would have answered, but never sends to it."""
        return await self._call("POST", "/chats/api/sending", {"chatId": str(chat_id), "on": on})

    async def reset(self, chat_id: int) -> dict[str, Any]:
        """Forgets the owner's own changes for this chat, so only Telegram folders decide."""
        return await self._call("POST", "/chats/api/reset", {"chatId": str(chat_id)})

    async def analysis(self, chat_id: int, limit: int = 100) -> dict[str, Any]:
        """What Brain made of this chat's messages: one item per agent run, with its decisions and proposed actions."""
        query = urllib.parse.urlencode({"chatId": str(chat_id), "limit": str(limit)})
        return await self._call("GET", f"/brain/api/chat-analysis?{query}")

    async def status(self) -> dict[str, Any]:
        return await self._call("GET", "/brain/api/status")

    async def decide(self, action_id: int, decision: str, text: str | None = None, reason: str | None = None) -> dict[str, Any]:
        """The owner's answer to something Brain proposed. Brain's own rules apply: nothing is sent without approve."""
        body: dict[str, Any] = {"id": action_id, "decision": decision}
        if text is not None:
            body["text"] = text
        if reason is not None:
            body["reason"] = reason
        return await self._call("POST", "/brain/api/decide", body)

    async def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.token()
        if not token:
            raise BrainError(503, NO_TOKEN.format(path=self.config.env_path))
        return await asyncio.to_thread(self._request, method, path, body, token)

    def _request(self, method: str, path: str, body: dict[str, Any] | None, token: str) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.config.url.rstrip("/") + path, data=data, method=method)
        request.add_header("x-brain-token", token)
        if data is not None:
            request.add_header("content-type", "application/json")
        try:
            with DIRECT.open(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise _from_http(error) from error
        except TimeoutError as error:
            raise BrainError(504, SLOW) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise BrainError(504, SLOW) from error
            raise BrainError(503, NOT_RUNNING) from error
        except ConnectionError as error:
            raise BrainError(503, NOT_RUNNING) from error


def _from_http(error: urllib.error.HTTPError) -> BrainError:
    try:
        payload = json.loads(error.read() or b"{}")
    except ValueError:
        payload = {}
    message = str(payload.get("error") or "")
    if error.code == 403:
        return BrainError(502, BAD_TOKEN)
    if error.code == 404 and payload.get("code") == "no-brain":
        return BrainError(503, NOT_RUNNING)
    if error.code == 400 and message:
        return BrainError(400, message)
    return BrainError(502, f"Brain answered with error {error.code}. {message}".strip())
