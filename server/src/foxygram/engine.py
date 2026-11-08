"""Calls Claude through the Claude Code CLI on your own login, so usage counts toward your plan.

Incoming messages are written by strangers. The CLI therefore runs with no tools, no MCP servers,
no settings and an empty working folder; the text travels only over stdin; and the answer is
treated as untrusted data that may only set labels (see analysis.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ClaudeConfig
from .db import Database, now
from .process import NO_WINDOW

log = logging.getLogger("engine")

LIMIT_PATTERN = re.compile(r"(usage limit|rate limit|limit reached|out of (extra )?usage|hit your .*limit)", re.I)
AUTH_PATTERN = re.compile(r"(not logged in|please run /login|authentication|oauth|invalid api key)", re.I)

LIMIT_BACKOFF_SECONDS = 3600
FAILURE_BACKOFF_SECONDS = 60


class EngineError(Exception):
    """A single call failed and may be retried."""


class EnginePaused(Exception):
    """Calls must stop for a while; the burst stays queued."""


@dataclass(frozen=True)
class EngineStatus:
    state: str
    detail: str
    resume_at: int
    calls_last_hour: int
    calls_today: int


def resolve_command(command: str) -> Path:
    """Find the real executable. npm's claude.cmd must not be used: it would route arguments through cmd.exe."""
    found = shutil.which(command)
    if not found:
        raise FileNotFoundError(f"{command} is not on PATH")
    path = Path(found)
    if path.suffix.lower() in {".cmd", ".bat", ""}:
        native = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if native.exists():
            return native
    return path


def build_arguments(config: ClaudeConfig, schema: dict[str, Any], system_prompt: str) -> list[str]:
    return [
        "-p",
        "--model", config.model,
        "--effort", config.effort,
        "--output-format", "json",
        "--json-schema", json.dumps(schema, separators=(",", ":")),
        "--system-prompt", system_prompt,
        "--tools", "",
        "--strict-mcp-config",
        "--setting-sources", "",
        "--no-session-persistence",
        "--permission-prompts", "none",
    ]


class ClaudeEngine:
    def __init__(self, config: ClaudeConfig, db: Database, sandbox: Path):
        self.config = config
        self.db = db
        self.sandbox = sandbox
        self._resume_at = 0
        self._state = "ok"
        self._detail = ""

    def status(self) -> EngineStatus:
        return EngineStatus(self._state_now(), self._detail, self._resume_at, *self._counts())

    def _state_now(self) -> str:
        if self._resume_at and time.time() >= self._resume_at:
            self._resume_at = 0
            self._state = "ok"
            self._detail = ""
        return self._state

    def _counts(self) -> tuple[int, int]:
        current = now()
        hour = self.db.scalar("SELECT COUNT(*) FROM claude_calls WHERE at >= ?", (current - 3600,))
        day = self.db.scalar("SELECT COUNT(*) FROM claude_calls WHERE at >= ?", (current - 86400,))
        return int(hour or 0), int(day or 0)

    def _pause(self, state: str, detail: str, seconds: int) -> None:
        self._state = state
        self._detail = detail
        self._resume_at = int(time.time()) + seconds
        log.warning("engine paused (%s) for %ss: %s", state, seconds, detail)

    def _check_gates(self) -> None:
        state = self._state_now()
        if state != "ok":
            raise EnginePaused(self._detail)
        hour, day = self._counts()
        if hour >= self.config.max_calls_per_hour:
            self._pause("capped", "Достигнут лимит вызовов в час", 300)
            raise EnginePaused(self._detail)
        if day >= self.config.max_calls_per_day:
            self._pause("capped", "Достигнут лимит вызовов в день", 1800)
            raise EnginePaused(self._detail)

    def _record(self, ok: bool, usage: dict[str, Any], duration_ms: int) -> None:
        self.db.execute(
            "INSERT INTO claude_calls(at, ok, input_tokens, output_tokens, duration_ms) VALUES(?,?,?,?,?)",
            (
                now(),
                int(ok),
                int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0)),
                int(usage.get("output_tokens", 0)),
                duration_ms,
            ),
        )

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        # A stray key would silently switch billing from your plan to the API.
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        return env

    async def run(self, system_prompt: str, schema: dict[str, Any], user_input: str) -> dict[str, Any]:
        self._check_gates()
        try:
            executable = resolve_command(self.config.command)
        except FileNotFoundError as error:
            self._pause("missing", str(error), 600)
            raise EnginePaused(str(error)) from error

        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            str(executable),
            *build_arguments(self.config, schema, system_prompt),
            cwd=str(self.sandbox),
            env=self._environment(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=NO_WINDOW,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(user_input.encode("utf-8")), self.config.timeout_seconds
            )
        except asyncio.TimeoutError as error:
            process.kill()
            await process.wait()
            self._record(False, {}, int((time.monotonic() - started) * 1000))
            raise EngineError("timed out") from error
        duration_ms = int((time.monotonic() - started) * 1000)

        try:
            payload = json.loads(stdout.decode("utf-8", "replace"))
        except json.JSONDecodeError as error:
            self._record(False, {}, duration_ms)
            detail = stderr.decode("utf-8", "replace")[:300] or stdout.decode("utf-8", "replace")[:300]
            self._classify(detail)
            raise EngineError(f"unreadable output: {detail}") from error

        usage = payload.get("usage") or {}
        result_text = str(payload.get("result") or "")
        output = payload.get("structured_output")
        if process.returncode != 0 or payload.get("is_error") or not isinstance(output, dict):
            # A login failure happens before any model call, so it costs nothing to log it.
            self._record(False, usage, duration_ms)
            self._classify(result_text)
            raise EngineError(result_text[:300] or f"exit code {process.returncode}")

        self._record(True, usage, duration_ms)
        return output

    def _classify(self, detail: str) -> None:
        if AUTH_PATTERN.search(detail):
            self._pause("login_needed", "Claude не авторизован: выполните claude auth login", 300)
            raise EnginePaused(self._detail)
        if LIMIT_PATTERN.search(detail):
            self._pause("quota", "Достигнут лимит Claude: анализ продолжится позже", LIMIT_BACKOFF_SECONDS)
            raise EnginePaused(self._detail)
