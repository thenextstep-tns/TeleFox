"""Settings live in one folder next to the data, so the server is a single unpack-and-run unit."""
from __future__ import annotations

import json
import os
import secrets
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_CONFIG = """\
# FoxyGram server settings. Restart the server after editing.

[telegram]
api_id = {api_id}
api_hash = "{api_hash}"

[server]
# The phone talks to api_port, usually through the tunnel.
api_port = 8787
# The control page. Only ever reachable from this computer.
admin_port = 8788
# The fixed public address of api_port, if you have one.
public_url = ""

[tunnel]
# "quick" starts a free temporary Cloudflare address.
# "named" runs your own Cloudflare tunnel for public_url, using the two settings below.
# "none" leaves it to you.
mode = "quick"
cloudflared = "cloudflared"
tunnel_id = ""
credentials_file = ""

[claude]
command = "claude"
# Every call counts against your weekly Claude quota.
model = "claude-haiku-5-5"
effort = "low"
max_calls_per_hour = 60
max_calls_per_day = 400
timeout_seconds = 120

[bursts]
# A burst closes after this many quiet seconds...
quiet_seconds = 60
# ...or when it gets this old or this long.
max_seconds = 300
max_messages = 30

[cases]
# Below this confidence an AI link waits in the review list.
min_confidence = 0.6
"""


def default_home() -> Path:
    override = os.environ.get("FOXYGRAM_HOME")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "FoxyGram"


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int = 0
    api_hash: str = ""


@dataclass(frozen=True)
class ServerConfig:
    api_port: int = 8787
    admin_port: int = 8788
    public_url: str = ""


@dataclass(frozen=True)
class TunnelConfig:
    mode: str = "quick"
    cloudflared: str = "cloudflared"
    tunnel_id: str = ""
    credentials_file: str = ""


@dataclass(frozen=True)
class ClaudeConfig:
    command: str = "claude"
    model: str = "claude-haiku-5-5"
    effort: str = "low"
    max_calls_per_hour: int = 60
    max_calls_per_day: int = 400
    timeout_seconds: int = 120


@dataclass(frozen=True)
class BurstConfig:
    quiet_seconds: int = 60
    max_seconds: int = 300
    max_messages: int = 30


@dataclass(frozen=True)
class CaseConfig:
    min_confidence: float = 0.6


@dataclass(frozen=True)
class Secrets:
    """Generated once; handed to the phone only through the pairing code."""

    api_token: str


@dataclass(frozen=True)
class Config:
    home: Path
    secrets: Secrets
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    tunnel: TunnelConfig = field(default_factory=TunnelConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    bursts: BurstConfig = field(default_factory=BurstConfig)
    cases: CaseConfig = field(default_factory=CaseConfig)

    @property
    def db_path(self) -> Path:
        return self.home / "foxygram.db"

    @property
    def tdlib_dir(self) -> Path:
        return self.home / "tdlib"

    @property
    def log_dir(self) -> Path:
        return self.home / "logs"

    @property
    def cloudflared_config(self) -> Path:
        return self.home / "cloudflared.yml"

    @property
    def sandbox_dir(self) -> Path:
        """Empty folder Claude runs in, so no project files or settings are picked up."""
        return self.home / "claude-sandbox"


def _load_secrets(home: Path) -> Secrets:
    path = home / "secrets.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Secrets(raw["api_token"])
    created = Secrets(secrets.token_urlsafe(32))
    path.write_text(json.dumps({"api_token": created.api_token}), encoding="utf-8")
    return created


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def ensure_config(home: Path, env_file: Path | None = None) -> Path:
    """Create config.toml on first run, taking the Telegram app id from an existing .env if given."""
    home.mkdir(parents=True, exist_ok=True)
    path = home / "config.toml"
    if not path.exists():
        env = read_env_file(env_file) if env_file and env_file.exists() else {}
        path.write_text(
            DEFAULT_CONFIG.format(
                api_id=int(env.get("TELEGRAM_API_ID") or 0),
                api_hash=env.get("TELEGRAM_API_HASH", ""),
            ),
            encoding="utf-8",
        )
    return path


def _tunnel_settings(raw: dict, home: Path) -> TunnelConfig:
    """A relative credentials file lives in the data folder, so the folder can move between computers."""
    tunnel = TunnelConfig(**raw)
    if tunnel.credentials_file and not Path(tunnel.credentials_file).is_absolute():
        return replace(tunnel, credentials_file=(home / tunnel.credentials_file).as_posix())
    return tunnel


def load_config(home: Path | None = None, env_file: Path | None = None) -> Config:
    home = home or default_home()
    path = ensure_config(home, env_file)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for sub in ("tdlib", "logs", "claude-sandbox"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    return Config(
        home=home,
        secrets=_load_secrets(home),
        telegram=TelegramConfig(**data.get("telegram", {})),
        server=ServerConfig(**data.get("server", {})),
        tunnel=_tunnel_settings(data.get("tunnel", {}), home),
        claude=ClaudeConfig(**data.get("claude", {})),
        bursts=BurstConfig(**data.get("bursts", {})),
        cases=CaseConfig(**data.get("cases", {})),
    )
