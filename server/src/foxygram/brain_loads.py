"""The loads Brain follows in a chat, shaped for the Brain panel in the browser and the phone app.

Brain's Loads tab has the full view. Here each load becomes a card the clients only have to draw: its stage and
progress, route, documents, what someone is still waiting for, numbers and its latest history. Times become Brain's
usual "YYYY-MM-DD HH:MM:SS" in this PC's local time, and message ids become TDLib's, like the rest of the panel.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .brain import to_tdlib

# Documents every load needs by a stage, shown as "not yet" until Brain records something. Seal and tarp aren't on
# every load, so they only show once recorded. The same rule as Brain's Loads tab.
DUE = {"rate_con": "posted", "bol": "loaded", "freight_photos": "loaded", "pod": "pod"}
EVENTS = 10
CLOSED = 3
OLD_WAIT_SECONDS = 4 * 3600


def _moment(iso: Any) -> datetime | None:
    text = str(iso or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def local(iso: Any) -> str:
    """Brain stores load times in UTC; the panel shows every Brain time in this PC's local time."""
    moment = _moment(iso)
    return moment.astimezone().strftime("%Y-%m-%d %H:%M:%S") if moment else ""


def ago(iso: Any, now: datetime) -> str:
    moment = _moment(iso)
    if not moment:
        return ""
    seconds = max(0.0, (now - moment).total_seconds())
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return f"{round(seconds / 60)} min ago"
    if seconds < 172800:
        return f"{round(seconds / 3600)} h ago"
    return f"{round(seconds / 86400)} days ago"


def _miles(miles: str) -> str:
    if not miles:
        return ""
    return f"{miles} mi" if re.fullmatch(r"\d[\d,.]*", miles) else f"Miles: {miles}"


def _stop(stop: dict[str, Any]) -> dict[str, Any]:
    kind = str(stop.get("type") or "stop")
    when = f" · {stop['when']}" if stop.get("when") else ""
    return {"text": f"{kind[:1].upper()}{kind[1:]}: {stop.get('place') or ''}{when}", "done": bool(stop.get("done"))}


def load_card(board: dict[str, Any], load: dict[str, Any], now: datetime) -> dict[str, Any]:
    stages = board.get("stages") or []
    order = [s.get("id") for s in stages]
    stage_id = str(load.get("stage") or "")
    index = order.index(stage_id) if stage_id in order else -1
    stage = stages[index] if index >= 0 else {"id": stage_id, "title": stage_id, "about": ""}
    is_open = bool(load.get("open"))
    stops = load.get("stops") or []
    places = [str(s.get("place") or "") for s in stops if s.get("place")]
    route = str(load.get("title") or "") or (" → ".join([places[0], places[-1]]) if len(places) > 1 else (places[0] if places else ""))
    meta = [
        f"Truck {load['truck']}" if load.get("truck") else "",
        str(load.get("driver") or ""),
        f"Broker {load['broker']}" if load.get("broker") else "",
        _miles(str(load.get("miles") or "")),
    ]

    states = board.get("checkStates") or {}
    recorded = load.get("checks") or {}
    checks = []
    for check in board.get("checks") or []:
        value = recorded.get(check.get("id"))
        title = str(check.get("title") or check.get("id"))
        if not value:
            due = DUE.get(check.get("id"))
            if due and is_open and due in order and index >= order.index(due):
                checks.append({"label": f"{title}: not yet", "tone": "missing", "detail": "Nothing recorded yet"})
            continue
        state = str(value.get("state") or "")
        mark = "✓ " if state in ("ok", "received") else "! " if state == "problem" else ""
        suffix = " (asked for)" if state == "asked" else " (not needed)" if state == "not_needed" else ""
        note = f" — {value['note']}" if value.get("note") else ""
        tone = {"problem": "problem", "asked": "asked", "not_needed": "plain"}.get(state, "ok")
        when = local(value.get("at"))
        checks.append({"label": f"{mark}{title}{suffix}{note}", "tone": tone,
                       "detail": f"{states.get(state, state)}{', ' + when if when else ''}"})

    waiting = []
    for wait in load.get("waiting") or []:
        if wait.get("doneAt"):
            continue
        moment = _moment(wait.get("at"))
        line = [f"from {wait['from']}" if wait.get("from") else "", f"asked by {wait['askedBy']}" if wait.get("askedBy") else "",
                ago(wait.get("at"), now)]
        waiting.append({"what": str(wait.get("what") or ""), "line": " · ".join(x for x in line if x), "at": local(wait.get("at")),
                        "old": bool(moment and (now - moment).total_seconds() > OLD_WAIT_SECONDS)})

    titles = {s.get("id"): s.get("title") for s in stages}
    events = []
    for event in (load.get("events") or [])[-EVENTS:]:
        telegram_ids = [int(m) for m in event.get("messageIds") or []]
        events.append({
            "text": str(event.get("text") or ""), "by": event.get("by") or "brain", "at": local(event.get("at")),
            "stage": titles.get(event.get("stage")) if event.get("stage") else None, "runId": event.get("runId"),
            "telegramMessageIds": telegram_ids, "messageIds": [to_tdlib(m) for m in telegram_ids],
        })

    numbers = load.get("numbers") or {}
    steps = len([s for s in stages if s.get("id") != "cancelled"])
    return {
        "id": load.get("id"),
        "name": f"Load {load['ref']}" if load.get("ref") else f"Load #{load.get('id')}",
        "ref": str(load.get("ref") or ""),
        "job": load.get("job"),
        "jobName": load.get("jobName") or load.get("job"),
        "stage": stage_id,
        "stageTitle": stage.get("title") or stage_id,
        "stageAbout": stage.get("about") or "",
        # 1..steps along the way; 0 when cancelled or unknown.
        "step": index + 1 if index >= 0 and stage_id != "cancelled" else 0,
        "steps": steps,
        "open": is_open,
        "route": route,
        "meta": [x for x in meta if x],
        "stops": [_stop(s) for s in stops],
        "checks": checks,
        "waiting": waiting,
        "numbers": [{"label": str(k), "value": str(v)} for k, v in numbers.items()],
        "events": events,
        "updatedAt": local(load.get("updatedAt")),
        "updatedAgo": ago(load.get("updatedAt"), now),
        "closedAt": local(load.get("closedAt")) if load.get("closedAt") else None,
    }


def panel_loads(board: dict[str, Any] | None, chat_id: Any, chat_jobs: list[str],
                now: datetime | None = None) -> list[dict[str, Any]] | None:
    """None when no job of this chat follows loads (or Brain can't say); otherwise its open loads and the last closed ones."""
    if not board:
        return None
    jobs = set(chat_jobs) & {j.get("id") for j in board.get("jobs") or []}
    if not jobs:
        return None
    now = now or datetime.now(timezone.utc)
    # A Brain that doesn't filter by chat yet answers with every chat's loads: only this chat's are shown.
    loads = [load for load in board.get("loads") or [] if load.get("job") in jobs and str(load.get("chatId")) == str(chat_id)]
    shown = [load for load in loads if load.get("open")] + [load for load in loads if not load.get("open")][:CLOSED]
    return [load_card(board, load, now) for load in shown]
