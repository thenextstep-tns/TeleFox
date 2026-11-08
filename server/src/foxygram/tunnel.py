"""Keeps a free outbound-only Cloudflare address pointing at the phone API."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil

from .config import ServerConfig, TunnelConfig

log = logging.getLogger("tunnel")

QUICK_URL = re.compile(rb"https://[a-z0-9-]+\.trycloudflare\.com")
RESTART_SECONDS = 15


class Tunnel:
    def __init__(self, tunnel: TunnelConfig, server: ServerConfig):
        self.config = tunnel
        self.server = server
        self.url = server.public_url
        self._process: asyncio.subprocess.Process | None = None

    async def run(self, stop: asyncio.Event) -> None:
        if self.server.public_url or self.config.mode != "quick":
            return
        executable = shutil.which(self.config.cloudflared)
        if not executable:
            log.error("cloudflared not found")
            return
        while not stop.is_set():
            self._process = await asyncio.create_subprocess_exec(
                executable, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.server.api_port}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            assert self._process.stderr is not None
            async for line in self._process.stderr:
                match = QUICK_URL.search(line)
                if match and match.group(0).decode() != self.url:
                    self.url = match.group(0).decode()
                    log.info("tunnel address: %s", self.url)
            await self._process.wait()
            log.warning("tunnel exited; restarting")
            try:
                await asyncio.wait_for(stop.wait(), RESTART_SECONDS)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
