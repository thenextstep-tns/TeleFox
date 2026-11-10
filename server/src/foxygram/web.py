"""The browser client: the phone app's screens, served on the local-only control port.

It reads and sends through the server's own Telegram session, and reuses the phone's /v1 routes for cases,
labels and the review queue. The control page's Host and CSRF checks cover every route here too.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Awaitable, TypeVar

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from . import __version__
from . import web_model as model
from .api import FLAGS_SQL, add_v1_routes
from .service import Service
from .telegram.tdjson import TdError
from .web_page import PAGE

PAGE_LIMIT = 100
MAX_TEXT = 4096
MAX_READ_IDS = 200
PING_SECONDS = 15
LIST_KEY = re.compile(r"^(main|archive|folder\d{1,10})$")
# Shown in place (photos, voice, video). Everything else, SVG included, is only ever downloaded.
INLINE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
INLINE_PREFIXES = ("audio/", "video/")
CSP = (
    "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

for extension, kind in ((".oga", "audio/ogg"), (".ogg", "audio/ogg"), (".opus", "audio/ogg"), (".webp", "image/webp"),
                        (".webm", "video/webm"), (".mp4", "video/mp4"), (".m4a", "audio/mp4")):
    mimetypes.add_type(kind, extension)

T = TypeVar("T")


class SendBody(BaseModel):
    text: str
    reply_to: int = 0


class ReadBody(BaseModel):
    ids: list[int]


class ChatSettings(BaseModel):
    list: str = "main"
    pinned: bool | None = None
    muted: bool | None = None
    archived: bool | None = None
    unread: bool | None = None


async def same_origin(request: Request) -> None:
    """Browsers say which site a request comes from. Only this page may use these routes."""
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        raise HTTPException(status_code=403, detail="forbidden")


async def td(call: Awaitable[T]) -> T:
    try:
        return await call
    except TdError as error:
        raise HTTPException(status_code=400, detail=error.message) from error


def label_of(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "needs_reply": bool(row.get("needs_reply")),
        "urgent": row.get("urgency") == "high",
        "ai": bool(row.get("ai_enabled")),
        "project": row.get("project_name"),
        "project_color": row.get("project_color"),
        "category": row.get("category_name"),
        "case_id": row.get("case_id"),
        "case_title": row.get("case_title"),
    }


def list_key_param(value: str) -> str:
    if not LIST_KEY.match(value):
        raise HTTPException(status_code=400, detail="unknown list")
    return value


def add_web_routes(app: FastAPI, service: Service) -> None:
    session = service.session
    store = session.store
    guard = [Depends(same_origin)]
    opened: set[int] = set()

    # Cases, labels, review and the Claude chat list, exactly as the phone gets them, minus the phone's token.
    add_v1_routes(app, service, guard)

    def ready() -> None:
        if session.auth.state != "ready":
            raise HTTPException(status_code=503, detail="telegram is not signed in")

    async def chat_of(chat_id: int) -> dict[str, Any]:
        chat = store.chats.get(chat_id)
        if chat is None:
            try:
                await session.client.call({"@type": "getChat", "chat_id": chat_id})
            except TdError:
                pass
            chat = store.chats.get(chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="unknown chat")
        return chat

    def labels() -> dict[int, dict[str, Any]]:
        return {row["chat_id"]: label_of(row) for row in service.db.all(FLAGS_SQL)}

    async def close_opened() -> None:
        for chat_id in list(opened):
            opened.discard(chat_id)
            try:
                await session.close_chat(chat_id)
            except TdError:
                pass

    @app.get("/app", response_class=HTMLResponse)
    async def page() -> HTMLResponse:
        return HTMLResponse(PAGE, headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": CSP,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        })

    @app.get("/app/api/state", dependencies=guard)
    async def state() -> dict[str, Any]:
        me = model.sender(store, {"@type": "messageSenderUser", "user_id": store.my_id}) if store.my_id else None
        return {
            "version": __version__,
            "telegram": session.auth.state,
            "connection": model.connection_label(session.auth.connection),
            "me": me,
            "folders": model.folder_tabs(store),
        }

    @app.get("/app/api/chats", dependencies=guard)
    async def chats(key: str = Query("main", alias="list")) -> dict[str, Any]:
        key = list_key_param(key)
        marks = labels()
        return {
            "chats": [model.chat_item(store, chat, key, marks.get(chat["id"])) for chat in store.ordered(key)],
            "folders": model.folder_tabs(store),
            "connection": model.connection_label(session.auth.connection),
        }

    @app.get("/app/api/search", dependencies=guard)
    async def search(q: str = "") -> dict[str, Any]:
        ready()
        if not q.strip():
            return {"chats": []}
        marks = labels()
        found = []
        for chat_id in await td(session.search_chats(q.strip())):
            chat = store.chats.get(chat_id)
            if chat is not None:
                found.append(model.chat_item(store, chat, "main", marks.get(chat_id)))
        return {"chats": found}

    @app.get("/app/api/chats/{chat_id}", dependencies=guard)
    async def chat(chat_id: int) -> dict[str, Any]:
        found = await chat_of(chat_id)
        return {
            "chat": model.chat_item(store, found, "main", labels().get(chat_id)),
            "subtitle": model.subtitle(store, found),
            "last_read_inbox": found.get("last_read_inbox_message_id", 0),
        }

    @app.get("/app/api/chats/{chat_id}/messages", dependencies=guard)
    async def messages(chat_id: int, from_id: int = Query(0, alias="from"), offset: int = 0, limit: int = 40) -> dict[str, Any]:
        ready()
        found = await chat_of(chat_id)
        limit = max(1, min(limit, PAGE_LIMIT))
        offset = max(-(limit - 1), min(offset, 0))
        page = await td(session.history_page(chat_id, from_id, offset, limit))
        by_id = {m["id"]: m for m in page}
        wanted = sorted({rid for m in page if (rid := model.replied_id(m)) and rid not in by_id})
        if wanted:
            try:
                by_id.update({m["id"]: m for m in await session.messages(chat_id, wanted)})
            except TdError:
                pass
        return {"messages": [model.message_item(store, found, m, by_id.get(model.replied_id(m))) for m in page]}

    @app.post("/app/api/chats/{chat_id}/open", dependencies=guard)
    async def open_chat(chat_id: int) -> dict[str, bool]:
        ready()
        await chat_of(chat_id)
        await td(session.open_chat(chat_id))
        opened.add(chat_id)
        return {"ok": True}

    @app.post("/app/api/chats/{chat_id}/close", dependencies=guard)
    async def close_chat(chat_id: int) -> dict[str, bool]:
        if chat_id in opened:
            opened.discard(chat_id)
            await td(session.close_chat(chat_id))
        return {"ok": True}

    @app.post("/app/api/chats/{chat_id}/read", dependencies=guard)
    async def read(chat_id: int, body: ReadBody) -> dict[str, bool]:
        ready()
        await chat_of(chat_id)
        ids = [i for i in body.ids if i > 0][:MAX_READ_IDS]
        if ids:
            await td(session.view_messages(chat_id, ids))
        return {"ok": True}

    @app.post("/app/api/chats/{chat_id}/send", dependencies=guard)
    async def send(chat_id: int, body: SendBody) -> dict[str, Any]:
        ready()
        found = await chat_of(chat_id)
        text = body.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="empty message")
        if len(text) > MAX_TEXT:
            raise HTTPException(status_code=400, detail="message too long")
        sent = await td(session.send_text(chat_id, text, max(body.reply_to, 0)))
        return {"message": model.message_item(store, found, sent)}

    @app.post("/app/api/chats/{chat_id}/settings", dependencies=guard)
    async def settings(chat_id: int, body: ChatSettings) -> dict[str, bool]:
        ready()
        await chat_of(chat_id)
        if body.unread is True:
            await td(session.mark_unread(chat_id))
        elif body.unread is False:
            await td(session.mark_read(chat_id))
        if body.pinned is not None:
            await td(session.set_pinned(chat_id, body.pinned, list_key_param(body.list)))
        if body.muted is not None:
            await td(session.set_muted(chat_id, body.muted))
        if body.archived is not None:
            await td(session.set_archived(chat_id, body.archived))
        return {"ok": True}

    @app.post("/app/api/lists/{key}/read", dependencies=guard)
    async def read_list(key: str) -> dict[str, bool]:
        ready()
        await td(session.read_chat_list(list_key_param(key)))
        return {"ok": True}

    @app.get("/app/api/files/{file_id}", dependencies=guard)
    async def file(file_id: int, name: str = "", download: bool = False) -> FileResponse:
        ready()
        try:
            info = await session.download(file_id)
        except (TdError, TimeoutError) as error:
            raise HTTPException(status_code=404, detail="file not available") from error
        local = info.get("local") or {}
        path = local.get("path") or ""
        if not path or not local.get("is_downloading_completed"):
            raise HTTPException(status_code=404, detail="file not available")
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(service.config.tdlib_dir.resolve()) or not resolved.is_file():
            raise HTTPException(status_code=404, detail="file not available")
        filename = Path(name).name or resolved.name
        media = mimetypes.guess_type(filename)[0] or mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        headers = {"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"}
        inline = media in INLINE_TYPES or media.startswith(INLINE_PREFIXES)
        if download or not inline:
            return FileResponse(resolved, media_type=media if inline else "application/octet-stream",
                                filename=filename, headers=headers)
        return FileResponse(resolved, media_type=media, headers=headers)

    @app.get("/app/api/events", dependencies=guard)
    async def events() -> StreamingResponse:
        queue = service.events.subscribe()

        async def stream():
            try:
                yield "retry: 3000\n\n"
                while not service.stop.is_set():
                    try:
                        event = await asyncio.wait_for(queue.get(), PING_SECONDS)
                    except TimeoutError:
                        yield ": ping\n\n"
                        continue
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            finally:
                service.events.unsubscribe(queue)
                if not service.events.listeners and opened:
                    # The last tab went away, so nothing is looking at the chats it left open.
                    asyncio.get_running_loop().create_task(close_opened())

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
