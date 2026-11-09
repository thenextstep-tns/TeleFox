"""The control page. Bound to 127.0.0.1 on a port the tunnel never reaches."""
from __future__ import annotations

from typing import Any

import segno
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__
from .admin_page import PAGE
from .service import Service, pairing_uri

CSRF_HEADER = "x-foxygram"


class PhoneBody(BaseModel):
    phone: str


class CodeBody(BaseModel):
    code: str


class PasswordBody(BaseModel):
    password: str


class ToggleBody(BaseModel):
    enabled: bool


def _svg(content: str) -> Response:
    qr = segno.make(content, error="m")
    return Response(qr.svg_inline(scale=5, border=2, dark="#000000", light="#ffffff"), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


def create_admin(service: Service) -> FastAPI:
    app = FastAPI(title="FoxyGram control", docs_url=None, redoc_url=None, openapi_url=None)
    port = service.config.server.admin_port
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    allowed_origins = {f"http://{host}" for host in allowed_hosts}

    class LocalOnly(BaseHTTPMiddleware):
        """Host stops DNS rebinding; the custom header stops other sites posting here."""

        async def dispatch(self, request: Request, call_next):
            if request.headers.get("host", "") not in allowed_hosts:
                return JSONResponse({"detail": "forbidden"}, status_code=403)
            if request.method != "GET":
                origin = request.headers.get("origin")
                if request.headers.get(CSRF_HEADER) != "1" or (origin and origin not in allowed_origins):
                    return JSONResponse({"detail": "forbidden"}, status_code=403)
            return await call_next(request)

    app.add_middleware(LocalOnly)

    def public_url() -> str:
        return service.config.server.public_url or service.tunnel.url

    @app.get("/", response_class=HTMLResponse)
    async def page() -> str:
        return PAGE

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        auth = service.session.auth
        engine = service.engine.status()
        db = service.db
        return {
            "version": __version__,
            "telegram": {
                "state": auth.state,
                "connection": auth.connection,
                "error": auth.error,
                "code_hint": auth.code_hint,
                "code_in_telegram": auth.code_in_telegram,
                "password_hint": auth.password_hint,
                "has_app_id": bool(service.config.telegram.api_id and service.config.telegram.api_hash),
            },
            "claude": {
                "state": engine.state,
                "detail": engine.detail,
                "model": service.config.claude.model,
                "calls_last_hour": engine.calls_last_hour,
                "calls_today": engine.calls_today,
                "max_per_hour": service.config.claude.max_calls_per_hour,
                "max_per_day": service.config.claude.max_calls_per_day,
            },
            "url": public_url(),
            "phone_seen_at": service.phone_seen_at,
            "selected": int(db.scalar("SELECT COUNT(*) FROM chats WHERE ai_enabled = 1") or 0),
            "pending": int(db.scalar("SELECT COUNT(*) FROM bursts WHERE status = 'pending'") or 0),
            "open_cases": int(db.scalar("SELECT COUNT(*) FROM cases WHERE status = 'open'") or 0),
        }

    @app.get("/api/qr/login.svg")
    async def login_qr() -> Response:
        if not service.session.auth.qr_link:
            raise HTTPException(status_code=404)
        return _svg(service.session.auth.qr_link)

    @app.get("/api/qr/pair.svg")
    async def pair_qr() -> Response:
        if not public_url():
            raise HTTPException(status_code=404)
        return _svg(pairing_uri(service.config, public_url()))

    @app.post("/api/login/qr")
    async def login_with_qr() -> dict[str, bool]:
        await service.session.login_qr()
        return {"ok": True}

    @app.post("/api/login/phone")
    async def login_phone(body: PhoneBody) -> dict[str, bool]:
        await service.session.login_phone(body.phone.strip())
        return {"ok": True}

    @app.post("/api/login/code")
    async def login_code(body: CodeBody) -> dict[str, bool]:
        await service.session.login_code(body.code.strip())
        return {"ok": True}

    @app.post("/api/login/password")
    async def login_password(body: PasswordBody) -> dict[str, bool]:
        await service.session.login_password(body.password)
        return {"ok": True}

    @app.get("/api/chats")
    async def chats() -> list[dict[str, Any]]:
        return service.db.all(
            "SELECT chat_id, title, kind, ai_enabled FROM chats WHERE title != '' ORDER BY ai_enabled DESC, title"
        )

    @app.post("/api/chats/{chat_id}/ai")
    async def toggle(chat_id: int, body: ToggleBody) -> dict[str, bool]:
        service.set_chat_ai(chat_id, body.enabled)
        return {"ok": True}

    return app
