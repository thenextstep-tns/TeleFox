"""Entry point: one process running the Telegram session, the phone API and the control page."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from .admin import create_admin
from .api import create_api
from .config import Config, load_config
from .service import Service

LOG_FILE_BYTES = 2_000_000
LOG_FILES_KEPT = 3


def _logging(config: Config) -> None:
    handler = RotatingFileHandler(
        config.log_dir / "server.log", maxBytes=LOG_FILE_BYTES, backupCount=LOG_FILES_KEPT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def serve(config: Config) -> None:
    service = Service(config)
    service.start()
    api = uvicorn.Server(uvicorn.Config(
        create_api(service), host="127.0.0.1", port=config.server.api_port, log_config=None, access_log=False))
    admin = uvicorn.Server(uvicorn.Config(
        create_admin(service), host="127.0.0.1", port=config.server.admin_port, log_config=None, access_log=False))
    for server in (api, admin):
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    def shutdown(*_: object) -> None:
        api.should_exit = True
        admin.should_exit = True

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), shutdown)
    try:
        await asyncio.gather(api.serve(), admin.serve())
    finally:
        await service.close()


def cli() -> None:
    parser = argparse.ArgumentParser(prog="foxygram-server")
    parser.add_argument("--home", type=Path, help="data folder (default %%LOCALAPPDATA%%\\FoxyGram)")
    parser.add_argument("--import-env", type=Path, help="read the Telegram app id from this .env on first run")
    args = parser.parse_args()
    config = load_config(args.home, args.import_env)
    _logging(config)
    asyncio.run(serve(config))


if __name__ == "__main__":
    cli()
