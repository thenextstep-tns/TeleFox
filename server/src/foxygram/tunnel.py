"""Keeps a free outbound-only Cloudflare address pointing at the phone API."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

from .config import ServerConfig, TunnelConfig
from .process import NO_WINDOW

log = logging.getLogger("tunnel")

# cloudflared also prints its own api.trycloudflare.com endpoint when a request fails.
QUICK_URL = re.compile(rb"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com")
RESTART_SECONDS = 15
OWN_CONFIG = "no-autoupdate: true\n"


class Tunnel:
    def __init__(self, tunnel: TunnelConfig, server: ServerConfig, config_file: Path):
        self.config = tunnel
        self.server = server
        self.config_file = config_file
        self.url = server.public_url
        self._process: asyncio.subprocess.Process | None = None

    def command(self, executable: str) -> list[str]:
        """Names our own config: by default cloudflared loads ~/.cloudflared/config.yml,
        whose ingress rules would replace --url and publish some other local service."""
        return [
            executable, "tunnel", "--config", str(self.config_file),
            "--url", f"http://127.0.0.1:{self.server.api_port}",
        ]

    def note_output(self, line: bytes) -> None:
        match = QUICK_URL.search(line)
        if match and match.group(0).decode() != self.url:
            self.url = match.group(0).decode()
            log.info("tunnel address: %s", self.url)

    async def run(self, stop: asyncio.Event) -> None:
        if self.server.public_url or self.config.mode != "quick":
            return
        executable = shutil.which(self.config.cloudflared)
        if not executable:
            log.error("cloudflared not found")
            return
        self.config_file.write_text(OWN_CONFIG, encoding="utf-8")
        while not stop.is_set():
            self._process = await asyncio.create_subprocess_exec(
                *self.command(executable),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                creationflags=NO_WINDOW,
            )
            assert self._process.stderr is not None
            async for line in self._process.stderr:
                self.note_output(line)
            await self._process.wait()
            log.warning("tunnel exited; restarting")
            try:
                await asyncio.wait_for(stop.wait(), RESTART_SECONDS)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
