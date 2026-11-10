"""The API the phone calls. Every route needs the token issued at pairing.

The browser client gets the same routes on the local-only control port, guarded there instead."""
from __future__ import annotations

import asyncio
import hmac
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from . import __version__
from .brain import BrainError, to_tdlib
from .db import now
from .service import Service

MAX_LIST = 200

FLAGS_SQL = """SELECT ch.chat_id, ch.needs_reply, ch.urgency, ch.ai_enabled, ch.project_id, ch.category_id,
          p.name AS project_name, p.color AS project_color, c.name AS category_name,
          (SELECT cs.id FROM cases cs JOIN case_links l ON l.case_id = cs.id JOIN bursts b ON b.id = l.burst_id
             WHERE b.chat_id = ch.chat_id AND cs.status = 'open' ORDER BY cs.updated_at DESC LIMIT 1) AS case_id,
          (SELECT cs.title FROM cases cs JOIN case_links l ON l.case_id = cs.id JOIN bursts b ON b.id = l.burst_id
             WHERE b.chat_id = ch.chat_id AND cs.status = 'open' ORDER BY cs.updated_at DESC LIMIT 1) AS case_title
   FROM chats ch
   LEFT JOIN projects p ON p.id = ch.project_id
   LEFT JOIN categories c ON c.id = ch.category_id
   WHERE ch.ai_enabled = 1 OR ch.project_id IS NOT NULL OR ch.needs_reply = 1"""


class ChatPatch(BaseModel):
    ai_enabled: bool | None = None
    project_id: int | None = None
    category_id: int | None = None


class ProjectBody(BaseModel):
    name: str
    color: str = "#a371f7"


class CategoryBody(BaseModel):
    name: str


class CasePatch(BaseModel):
    title: str | None = None
    status: str | None = None


class MergeBody(BaseModel):
    into: int


class MoveBody(BaseModel):
    case_id: int | None = None
    new_title: str | None = None


class BrainJobBody(BaseModel):
    job_id: str
    on: bool


class BrainDecision(BaseModel):
    decision: Literal["approve", "reject", "answer", "dismiss"]
    text: str | None = None
    reason: str | None = None


def brain_panel(chat: dict[str, Any], status: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """What the side panel next to a chat shows. Message ids are turned into TDLib's, which the clients use."""
    names = {job["id"]: job["name"] for job in chat.get("jobs") or []}
    paused = {job["id"] for job in status.get("jobs") or [] if job.get("paused")}
    items = []
    for item in analysis.get("items") or []:
        telegram_ids = [int(m) for m in item.get("messageIds") or []]
        items.append({**item, "telegramMessageIds": telegram_ids, "messageIds": [to_tdlib(m) for m in telegram_ids]})
    return {
        "active": True,
        "jobs": [{"id": job, "name": names.get(job, job), "paused": job in paused} for job in chat["chat"]["jobs"]],
        "items": items,
        # Messages Brain has received but not yet started on (it waits about 20 s for more), as TDLib ids.
        "waiting": [to_tdlib(int(m)) for m in analysis.get("waiting") or []],
    }


def _case_row(service: Service, case: dict[str, Any]) -> dict[str, Any]:
    chats = service.db.all(
        """SELECT DISTINCT b.chat_id, ch.title FROM case_links l
           JOIN bursts b ON b.id = l.burst_id LEFT JOIN chats ch ON ch.chat_id = b.chat_id
           WHERE l.case_id = ?""",
        (case["id"],),
    )
    case["chats"] = chats
    case["entities"] = service.db.all("SELECT type, value FROM case_entities WHERE case_id = ?", (case["id"],))
    case["needs_review"] = int(service.db.scalar(
        "SELECT COUNT(*) FROM case_links WHERE case_id = ? AND needs_review = 1", (case["id"],)) or 0)
    return case


def _record_correction(service: Service, burst_id: int, from_case: int | None, to_title: str | None) -> None:
    summary = service.db.scalar("SELECT summary FROM analyses WHERE burst_id = ?", (burst_id,)) or ""
    from_title = service.db.scalar("SELECT title FROM cases WHERE id = ?", (from_case,)) if from_case else None
    service.db.execute(
        "INSERT INTO corrections(created_at, burst_summary, from_case, to_case) VALUES(?,?,?,?)",
        (now(), summary, from_title, to_title),
    )


def create_api(service: Service) -> FastAPI:
    app = FastAPI(title="FoxyGram", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    expected = service.config.secrets.api_token

    async def require_token(authorization: str = Header(default="")) -> None:
        supplied = authorization.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="invalid token")
        service.phone_seen_at = now()

    add_v1_routes(app, service, [Depends(require_token)])
    return app


def add_v1_routes(app: FastAPI, service: Service, dependencies: list[Any]) -> None:
    """Every /v1 route, each carrying the given guard dependencies."""
    db = service.db
    guarded = {"dependencies": dependencies}

    @app.get("/v1/health", **guarded)
    async def health() -> dict[str, Any]:
        engine = service.engine.status()
        return {
            "version": __version__,
            "telegram": service.session.auth.state,
            "connection": service.session.auth.connection,
            "claude": {
                "state": engine.state,
                "detail": engine.detail,
                "calls_last_hour": engine.calls_last_hour,
                "calls_today": engine.calls_today,
            },
            "pending": int(db.scalar("SELECT COUNT(*) FROM bursts WHERE status = 'pending'") or 0),
        }

    @app.get("/v1/chats", **guarded)
    async def chats() -> list[dict[str, Any]]:
        return db.all(
            """SELECT chat_id, title, kind, ai_enabled, project_id, category_id, needs_reply, urgency
               FROM chats ORDER BY ai_enabled DESC, last_activity DESC, title"""
        )

    @app.api_route("/v1/chats/{chat_id}", methods=["PATCH", "POST"], **guarded)
    async def patch_chat(chat_id: int, body: ChatPatch) -> dict[str, bool]:
        if not db.scalar("SELECT 1 FROM chats WHERE chat_id = ?", (chat_id,)):
            raise HTTPException(status_code=404, detail="unknown chat")
        if body.ai_enabled is not None:
            service.set_chat_ai(chat_id, body.ai_enabled)
        if "project_id" in body.model_fields_set:
            db.execute("UPDATE chats SET project_id = ?, category_id = NULL WHERE chat_id = ?", (body.project_id, chat_id))
        if "category_id" in body.model_fields_set:
            db.execute("UPDATE chats SET category_id = ? WHERE chat_id = ?", (body.category_id, chat_id))
        return {"ok": True}

    @app.get("/v1/flags", **guarded)
    async def flags() -> list[dict[str, Any]]:
        """Compact per-chat labels for the chat list."""
        return db.all(FLAGS_SQL)

    @app.get("/v1/projects", **guarded)
    async def projects() -> list[dict[str, Any]]:
        rows = db.all("SELECT * FROM projects ORDER BY name")
        for row in rows:
            row["categories"] = db.all("SELECT id, name FROM categories WHERE project_id = ? ORDER BY name", (row["id"],))
        return rows

    @app.post("/v1/projects", **guarded)
    async def add_project(body: ProjectBody) -> dict[str, int]:
        try:
            cursor = db.execute("INSERT INTO projects(name, color) VALUES(?,?)", (body.name.strip(), body.color))
        except Exception as error:
            raise HTTPException(status_code=409, detail="project exists") from error
        return {"id": int(cursor.lastrowid)}

    @app.delete("/v1/projects/{project_id}", **guarded)
    async def delete_project(project_id: int) -> dict[str, bool]:
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return {"ok": True}

    @app.post("/v1/projects/{project_id}/categories", **guarded)
    async def add_category(project_id: int, body: CategoryBody) -> dict[str, int]:
        try:
            cursor = db.execute("INSERT INTO categories(project_id, name) VALUES(?,?)", (project_id, body.name.strip()))
        except Exception as error:
            raise HTTPException(status_code=409, detail="category exists") from error
        return {"id": int(cursor.lastrowid)}

    @app.delete("/v1/categories/{category_id}", **guarded)
    async def delete_category(category_id: int) -> dict[str, bool]:
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        return {"ok": True}

    @app.get("/v1/cases", **guarded)
    async def cases(status: str = "open", q: str = Query(default=""), limit: int = 100) -> list[dict[str, Any]]:
        limit = min(limit, MAX_LIST)
        if q.strip():
            query = " ".join(f'"{t}"*' for t in q.replace('"', " ").split())
            rows = db.all(
                """SELECT c.* FROM cases_fts f JOIN cases c ON c.id = f.rowid
                   WHERE cases_fts MATCH ? AND c.status = ? ORDER BY rank LIMIT ?""",
                (query, status, limit),
            )
        else:
            rows = db.all("SELECT * FROM cases WHERE status = ? ORDER BY updated_at DESC LIMIT ?", (status, limit))
        return [_case_row(service, row) for row in rows]

    @app.get("/v1/cases/{case_id}", **guarded)
    async def case_detail(case_id: int) -> dict[str, Any]:
        case = db.one("SELECT * FROM cases WHERE id = ?", (case_id,))
        if case is None:
            raise HTTPException(status_code=404, detail="unknown case")
        case = _case_row(service, case)
        timeline = db.all(
            """SELECT b.id AS burst_id, b.chat_id, b.created_at, ch.title AS chat_title,
                      a.intent, a.needs_reply, a.urgency, a.summary, l.source, l.confidence, l.needs_review
               FROM case_links l JOIN bursts b ON b.id = l.burst_id
               LEFT JOIN analyses a ON a.burst_id = b.id LEFT JOIN chats ch ON ch.chat_id = b.chat_id
               WHERE l.case_id = ? ORDER BY b.created_at DESC""",
            (case_id,),
        )
        for item in timeline:
            item["messages"] = db.all(
                """SELECT message_id, date, sender_name, outgoing, kind, text
                   FROM messages WHERE burst_id = ? ORDER BY date, message_id""",
                (item["burst_id"],),
            )
        case["timeline"] = timeline
        return case

    @app.api_route("/v1/cases/{case_id}", methods=["PATCH", "POST"], **guarded)
    async def patch_case(case_id: int, body: CasePatch) -> dict[str, bool]:
        if body.title is not None and body.title.strip():
            db.execute("UPDATE cases SET title = ? WHERE id = ?", (body.title.strip()[:60], case_id))
        if body.status in ("open", "closed"):
            db.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", (body.status, now(), case_id))
        return {"ok": True}

    @app.post("/v1/cases/{case_id}/merge", **guarded)
    async def merge_case(case_id: int, body: MergeBody) -> dict[str, bool]:
        if case_id == body.into or not db.scalar("SELECT 1 FROM cases WHERE id = ?", (body.into,)):
            raise HTTPException(status_code=400, detail="bad merge target")
        with db.transaction():
            db.execute("UPDATE case_links SET case_id = ?, source = 'user', needs_review = 0 WHERE case_id = ?", (body.into, case_id))
            db.execute(
                "INSERT OR IGNORE INTO case_entities(case_id, type, value) SELECT ?, type, value FROM case_entities WHERE case_id = ?",
                (body.into, case_id),
            )
            db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            db.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now(), body.into))
        return {"ok": True}

    @app.get("/v1/review", **guarded)
    async def review() -> list[dict[str, Any]]:
        return db.all(
            """SELECT l.burst_id, l.case_id, l.confidence, c.title AS case_title, a.summary, a.intent, ch.title AS chat_title
               FROM case_links l JOIN cases c ON c.id = l.case_id
               JOIN bursts b ON b.id = l.burst_id LEFT JOIN analyses a ON a.burst_id = l.burst_id
               LEFT JOIN chats ch ON ch.chat_id = b.chat_id
               WHERE l.needs_review = 1 ORDER BY b.created_at DESC LIMIT 100"""
        )

    @app.post("/v1/bursts/{burst_id}/confirm", **guarded)
    async def confirm(burst_id: int) -> dict[str, bool]:
        db.execute("UPDATE case_links SET needs_review = 0, source = 'user' WHERE burst_id = ?", (burst_id,))
        return {"ok": True}

    @app.post("/v1/bursts/{burst_id}/move", **guarded)
    async def move(burst_id: int, body: MoveBody) -> dict[str, Any]:
        if not db.scalar("SELECT 1 FROM bursts WHERE id = ?", (burst_id,)):
            raise HTTPException(status_code=404, detail="unknown burst")
        from_case = db.scalar("SELECT case_id FROM case_links WHERE burst_id = ?", (burst_id,))
        target = body.case_id
        current = now()
        if body.new_title and body.new_title.strip():
            cursor = db.execute(
                "INSERT INTO cases(title, summary, status, created_at, updated_at) VALUES(?, '', 'open', ?, ?)",
                (body.new_title.strip()[:60], current, current),
            )
            target = int(cursor.lastrowid)
        if target is None:
            db.execute("DELETE FROM case_links WHERE burst_id = ?", (burst_id,))
            _record_correction(service, burst_id, from_case, None)
            return {"case_id": None}
        title = db.scalar("SELECT title FROM cases WHERE id = ?", (target,))
        if title is None:
            raise HTTPException(status_code=404, detail="unknown case")
        db.execute(
            "INSERT OR REPLACE INTO case_links(burst_id, case_id, source, confidence, needs_review) VALUES(?,?, 'user', 1.0, 0)",
            (burst_id, target),
        )
        db.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (current, target))
        _record_correction(service, burst_id, from_case, title)
        return {"case_id": target}

    @app.get("/v1/search", **guarded)
    async def search(q: str, limit: int = 50) -> list[dict[str, Any]]:
        terms = " ".join(f'"{t}"*' for t in q.replace('"', " ").split())
        if not terms:
            return []
        return db.all(
            """SELECT m.chat_id, m.message_id, m.date, m.sender_name, m.outgoing, m.kind, m.text, ch.title AS chat_title
               FROM messages_fts f JOIN messages m ON m.id = f.rowid LEFT JOIN chats ch ON ch.chat_id = m.chat_id
               WHERE messages_fts MATCH ? ORDER BY m.date DESC LIMIT ?""",
            (terms, min(limit, MAX_LIST)),
        )

    # Brain jobs: which of Brain's jobs get a chat. The server asks Brain, so its token stays on this PC.
    async def brain(call):
        try:
            return await call
        except BrainError as error:
            raise HTTPException(status_code=error.status, detail=error.message) from error

    @app.get("/v1/brain/chats/{chat_id}", **guarded)
    async def brain_chat(chat_id: int) -> dict[str, Any]:
        return await brain(service.brain.chat(chat_id))

    @app.post("/v1/brain/chats/{chat_id}/jobs", **guarded)
    async def brain_assign(chat_id: int, body: BrainJobBody) -> dict[str, Any]:
        return await brain(service.brain.assign(chat_id, body.job_id, body.on))

    @app.post("/v1/brain/chats/{chat_id}/reset", **guarded)
    async def brain_reset(chat_id: int) -> dict[str, Any]:
        return await brain(service.brain.reset(chat_id))

    @app.get("/v1/brain/chats/{chat_id}/panel", **guarded)
    async def brain_chat_panel(chat_id: int, limit: int = 100) -> dict[str, Any]:
        """Brain's side panel for a chat: only for chats in at least one of Brain's jobs."""
        chat = await brain(service.brain.chat(chat_id))
        if not (chat.get("chat") or {}).get("jobs"):
            return {"active": False, "jobs": [], "items": []}
        status, analysis = await brain(asyncio.gather(
            service.brain.status(), service.brain.analysis(chat_id, max(1, min(limit, 500)))))
        return brain_panel(chat, status, analysis)

    @app.post("/v1/brain/actions/{action_id}/decide", **guarded)
    async def brain_decide(action_id: int, body: BrainDecision) -> dict[str, Any]:
        return await brain(service.brain.decide(action_id, body.decision, body.text, body.reason))
