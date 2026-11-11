"""Brain jobs: the server asks Brain which jobs get a chat, with a token that never leaves this PC."""
import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from foxygram.admin import create_admin
from foxygram.api import create_api
from foxygram.brain import Brain, BrainError
from foxygram.config import BrainConfig

TOKEN = "brain-token-for-test"
JOBS = [{"id": "job1", "name": "Job 1 - amoCRM"}, {"id": "job2", "name": "Job 2 - Datatruck"}]
ANALYSIS = {
    "runId": 6, "job": "job2", "jobName": "Job 2 - Datatruck", "at": "2026-11-10 18:31:18", "messageIds": [101, 102],
    "status": "done", "working": False,
    "decisions": [{"runId": 6, "at": "2026-11-10 18:31:18", "text": "This needs a reply."}],
    "actions": [{"id": 3, "runId": 6, "kind": "approval", "actionType": "telegram.send", "status": "open",
                 "statusText": "Waiting for you", "to": "Test Group", "text": "Got it", "question": None, "options": [],
                 "reason": "", "answer": None, "result": None, "createdAt": "2026-11-10 18:31:18", "resolvedAt": None}],
    "summary": "",
}
STAGES = [{"id": s, "title": t, "about": a} for s, t, a in [
    ("posted", "Posted", "The dispatcher posted the load."), ("tracking", "Tracking", "Tracking was mentioned."),
    ("pickup", "Pickup", "Driving to the shipper."), ("loaded", "Loaded", "Loaded at the shipper: BOL, freight photos, seal and tarp checks."),
    ("in_transit", "In transit", "On the way."), ("delivery", "Delivery", "ETA, arrived, unloading, empty."),
    ("pod", "POD", "Waiting for the POD."), ("done", "Done", "The POD came in clean."), ("cancelled", "Cancelled", "Fell through.")]]
CHECKS = [{"id": i, "title": t} for i, t in [
    ("rate_con", "Rate confirmation"), ("route", "Route & miles"), ("tracking", "Tracking mentioned"), ("pickup_number", "Pickup number"),
    ("bol", "BOL"), ("freight_photos", "Freight photos"), ("seal", "Seal number"), ("tarp", "Tarp photos"), ("pod", "POD"),
    ("datatruck", "Delivered in Datatruck")]]
# Brain's /brain/api/loads?show=all&chatId=… for "Truck 325": one load under way, one done, and one of another job.
LOAD = {
    "id": 4, "job": "job2", "chatId": "-5534970202", "chatTitle": "Truck 325", "ref": "", "title": "Le Roy, NY → Montgomery, AL",
    "truck": "325", "driver": "Shinara Matthews", "broker": "", "miles": "1119", "stage": "loaded",
    "stops": [{"type": "pickup", "place": "Le Roy, NY 14482", "when": "11/10 7:30-15:00", "done": True},
              {"type": "delivery", "place": "Montgomery, AL 36105", "when": "11/12 7:30"}],
    "numbers": {"Shipper BOL #": "32950027"},
    "checks": {"rate_con": {"state": "received", "note": "posted by Orest", "at": "2026-11-11T12:34:20.085Z"},
               "tracking": {"state": "asked", "note": "Trucker Tools", "at": "2026-11-11T12:34:20.085Z"},
               "bol": {"state": "problem", "note": "page 1 of 2 only", "at": "2026-11-11T12:34:20.085Z"}},
    "waiting": [{"id": 1, "what": "Trucker Tools screenshot", "from": "driver", "askedBy": "Orest", "at": "2026-11-10T16:00:45.000Z"},
                {"id": 2, "what": "Old request", "at": "2026-11-10T10:00:00.000Z", "doneAt": "2026-11-10T11:00:00.000Z"}],
    "createdAt": "2026-11-11T12:34:20.085Z", "updatedAt": "2026-11-11T12:34:20.085Z", "closedAt": None, "open": True,
    "jobName": "Dispatch Helper",
    "events": [{"id": 4, "loadId": 4, "runId": 99, "by": "brain", "text": "Caught up from the chat: loaded in Le Roy.",
                "stage": "loaded", "messageIds": [100, 101], "at": "2026-11-11T12:34:20.085Z"}],
}
DONE = {**LOAD, "id": 3, "ref": "77001", "title": "", "stage": "done", "open": False, "closedAt": "2026-11-10T20:00:00.000Z",
        "checks": {}, "waiting": [], "numbers": {}, "miles": "about 300",
        "events": [{"id": 3, "loadId": 3, "runId": None, "by": "owner", "text": "Moved to Done.", "stage": "done", "messageIds": [],
                    "at": "2026-11-10T20:00:00.000Z"}]}
BOARD = {"stages": STAGES, "checks": CHECKS, "checkStates": {"asked": "asked for", "received": "received", "ok": "checked, fine",
                                                             "problem": "problem", "not_needed": "not needed"},
         "jobs": [{"id": "job2", "name": "Dispatch Helper"}], "counts": {"loaded": 1}, "closed": 1, "catchingUp": 0, "chats": 4,
         "loads": [LOAD, DONE, {**LOAD, "id": 9, "job": "job7"}, {**LOAD, "id": 10, "chatId": "-100777"}]}


class FakeBrain(BaseHTTPRequestHandler):
    """Answers like Brain's /chats/api, and remembers what it was asked."""

    seen: list = []
    state: dict = {}

    def log_message(self, *_):
        pass

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def chat(self, chat_id):
        jobs = self.state.setdefault(chat_id, {"jobs": [], "added": []})
        return {"chatId": chat_id, "title": "Truck 342", "kind": "group", "account": "main", "folders": ["SA Trucking"],
                "jobs": jobs["jobs"], "viaFolder": ["job2"], "added": jobs["added"], "removed": [],
                "sending": chat_id not in self.state.get("noSend", set())}

    def handle_any(self, body):
        FakeBrain.seen.append({"method": self.command, "path": self.path, "token": self.headers.get("x-brain-token"),
                               "host": self.headers.get("host"), "body": body})
        if self.headers.get("x-brain-token") != TOKEN:
            return self.reply(403, {"error": "Open this page at http://localhost:7777/chats"})
        if self.path.startswith("/chats/api/chat?"):
            chat_id = self.path.split("chatId=")[1]
            return self.reply(200, {"jobs": JOBS, "connected": True, "chat": self.chat(chat_id)})
        if self.path.startswith("/brain/api/chat-analysis?"):
            return self.reply(200, {"chatId": "-5534970202", "items": [ANALYSIS], "waiting": [103]})
        if self.path.startswith("/brain/api/loads?") and not self.state.get("noLoads"):
            return self.reply(200, BOARD)
        if self.path == "/brain/api/status":
            return self.reply(200, {"jobs": [{"id": "job1", "paused": False}, {"id": "job2", "paused": True}], "running": 0, "open": 1})
        if self.path == "/brain/api/decide":
            if body.get("decision") == "answer" and not body.get("text"):
                return self.reply(400, {"error": "Write an answer first."})
            return self.reply(200, {"text": f"#{body['id']} {body['decision']}"})
        if self.path == "/chats/api/assign":
            if body["jobId"] not in {j["id"] for j in JOBS}:
                return self.reply(400, {"error": f'There is no job "{body["jobId"]}".'})
            jobs = self.state.setdefault(body["chatId"], {"jobs": [], "added": []})
            if body["on"]:
                jobs["jobs"].append(body["jobId"])
                jobs["added"].append(body["jobId"])
            return self.reply(200, {"text": "now goes to the job", "chat": self.chat(body["chatId"])})
        if self.path == "/chats/api/sending":
            off = self.state.setdefault("noSend", set())
            if body["on"]:
                off.discard(body["chatId"])
            else:
                off.add(body["chatId"])
            return self.reply(200, {"text": "Sending is off" if not body["on"] else "Sending is on", "chat": self.chat(body["chatId"])})
        if self.path == "/chats/api/reset":
            self.state.pop(body["chatId"], None)
            return self.reply(200, {"text": "follows its folders again", "chat": self.chat(body["chatId"])})
        return self.reply(404, {"error": "not found"})

    def do_GET(self):
        self.handle_any(None)

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        self.handle_any(json.loads(self.rfile.read(length) or b"{}"))


@pytest.fixture
def brain_url():
    FakeBrain.seen = []
    FakeBrain.state = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeBrain)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def brain_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"N8N_URL=http://localhost:5678\nBRAIN_TOKEN={TOKEN}\n", encoding="utf-8")
    return env


def use_brain(service, url, **settings):
    service.brain = Brain(BrainConfig(url=url, **settings))


async def test_the_token_comes_from_brains_env_file_and_ids_stay_in_telegrams_format(brain_url, brain_env):
    found = await Brain(BrainConfig(url=brain_url, env_file=str(brain_env))).chat(-1004430020815)
    assert found["jobs"] == JOBS
    asked = FakeBrain.seen[0]
    assert asked["token"] == TOKEN
    assert asked["path"] == "/chats/api/chat?chatId=-1004430020815"
    assert asked["host"] == brain_url.removeprefix("http://")


async def test_a_token_in_config_wins_over_the_env_file(brain_url, tmp_path):
    env = tmp_path / ".env"
    env.write_text("BRAIN_TOKEN=stale\n", encoding="utf-8")
    await Brain(BrainConfig(url=brain_url, env_file=str(env), token=TOKEN)).chat(1)
    assert FakeBrain.seen[0]["token"] == TOKEN


async def test_problems_come_back_in_plain_words(brain_url, tmp_path):
    with pytest.raises(BrainError) as missing:
        await Brain(BrainConfig(url=brain_url, env_file=str(tmp_path / "none.env"))).chat(1)
    assert missing.value.status == 503 and "BRAIN_TOKEN" in missing.value.message and FakeBrain.seen == []

    with pytest.raises(BrainError) as refused:
        await Brain(BrainConfig(url=brain_url, token="wrong")).chat(1)
    assert refused.value.status == 502 and "token" in refused.value.message

    with pytest.raises(BrainError) as bad_job:
        await Brain(BrainConfig(url=brain_url, token=TOKEN)).assign(1, "nope", True)
    assert bad_job.value.status == 400 and bad_job.value.message == 'There is no job "nope".'

    with pytest.raises(BrainError) as down:
        await Brain(BrainConfig(url="http://127.0.0.1:9", token=TOKEN)).chat(1)
    assert down.value.status == 503 and "isn't running" in down.value.message


async def test_the_phone_changes_jobs_through_the_server(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    transport = httpx.ASGITransport(app=create_api(service))
    headers = {"Authorization": f"Bearer {service.config.secrets.api_token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://x", headers=headers) as phone:
        body = (await phone.get("/v1/brain/chats/-623132203")).json()
        assert body["jobs"] == JOBS and body["chat"]["jobs"] == []
        body = (await phone.post("/v1/brain/chats/-623132203/jobs", json={"job_id": "job1", "on": True})).json()
        assert body["chat"]["jobs"] == ["job1"] and body["text"]
        assert FakeBrain.seen[-1]["body"] == {"chatId": "-623132203", "jobId": "job1", "on": True}
        body = (await phone.post("/v1/brain/chats/-623132203/reset")).json()
        assert body["chat"]["jobs"] == []
        refused = await phone.post("/v1/brain/chats/-623132203/jobs", json={"job_id": "nope", "on": True})
        assert refused.status_code == 400 and refused.json()["detail"] == 'There is no job "nope".'
    assert all(asked["token"] == TOKEN for asked in FakeBrain.seen)


async def test_brain_jobs_need_the_phone_token(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    transport = httpx.ASGITransport(app=create_api(service))
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as stranger:
        assert (await stranger.get("/v1/brain/chats/1")).status_code == 401
        assert (await stranger.post("/v1/brain/chats/1/jobs", json={"job_id": "job1", "on": True})).status_code == 401
    assert FakeBrain.seen == []


async def test_the_browser_changes_jobs_on_the_local_port(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as browser:
        assert (await browser.get("/v1/brain/chats/7")).json()["chat"]["jobs"] == []
        unguarded = await browser.post("/v1/brain/chats/7/jobs", json={"job_id": "job2", "on": True})
        assert unguarded.status_code == 403
        done = await browser.post("/v1/brain/chats/7/jobs", json={"job_id": "job2", "on": True}, headers={"x-foxygram": "1"})
        assert done.json()["chat"]["jobs"] == ["job2"]


async def test_a_stopped_brain_is_reported_not_crashed(service):
    use_brain(service, "http://127.0.0.1:9", token=TOKEN)
    transport = httpx.ASGITransport(app=create_api(service))
    headers = {"Authorization": f"Bearer {service.config.secrets.api_token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://x", headers=headers) as phone:
        response = await phone.get("/v1/brain/chats/1")
    assert response.status_code == 503 and "Brain isn't running" in response.json()["detail"]


def test_telegram_message_ids_become_tdlibs():
    from foxygram.brain import to_tdlib
    assert to_tdlib(114) == 119_537_664  # run #5, message 114 of "Truck 325", as TDLib numbers it
    assert to_tdlib(129446) == 129446 * 1_048_576


async def test_the_panel_shows_only_for_chats_in_a_job(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as browser:
        outside = (await browser.get("/v1/brain/chats/-5534970202/panel")).json()
        assert outside == {"active": False, "jobs": [], "items": []}
        assert not any(asked["path"].startswith("/brain/api/") for asked in FakeBrain.seen)

        await browser.post("/v1/brain/chats/-5534970202/jobs", json={"job_id": "job2", "on": True}, headers={"x-foxygram": "1"})
        panel = (await browser.get("/v1/brain/chats/-5534970202/panel")).json()
    assert panel["active"] is True
    assert panel["jobs"] == [{"id": "job2", "name": "Job 2 - Datatruck", "paused": True}]
    item = panel["items"][0]
    assert item["telegramMessageIds"] == [101, 102]
    assert item["messageIds"] == [101 << 20, 102 << 20]
    assert item["actions"][0]["text"] == "Got it" and item["decisions"][0]["text"] == "This needs a reply."
    assert panel["waiting"] == [103 << 20]  # received by Brain, not started yet
    assert panel["sending"] is True
    asked = [a["path"] for a in FakeBrain.seen]
    assert any(p.startswith("/brain/api/chat-analysis?chatId=-5534970202") for p in asked)


async def test_the_panel_shows_the_chats_loads(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as browser:
        await browser.post("/v1/brain/chats/-5534970202/jobs", json={"job_id": "job2", "on": True}, headers={"x-foxygram": "1"})
        panel = (await browser.get("/v1/brain/chats/-5534970202/panel")).json()
        assert "/brain/api/loads?show=all&chatId=-5534970202" in [a["path"] for a in FakeBrain.seen]
        load, done = panel["loads"]  # neither another job's load nor another chat's
        assert load["name"] == "Load #4" and load["stageTitle"] == "Loaded" and (load["step"], load["steps"]) == (4, 8)
        assert load["route"] == "Le Roy, NY → Montgomery, AL" and load["meta"] == ["Truck 325", "Shinara Matthews", "1119 mi"]
        assert load["stops"][0] == {"text": "Pickup: Le Roy, NY 14482 · 11/10 7:30-15:00", "done": True}
        labels = [(c["label"], c["tone"]) for c in load["checks"]]
        assert labels == [("✓ Rate confirmation — posted by Orest", "ok"), ("Tracking mentioned (asked for) — Trucker Tools", "asked"),
                          ("! BOL — page 1 of 2 only", "problem"), ("Freight photos: not yet", "missing")]
        assert [w["what"] for w in load["waiting"]] == ["Trucker Tools screenshot"]  # the done one is left out
        assert load["waiting"][0]["line"].startswith("from driver · asked by Orest · ") and load["waiting"][0]["line"].endswith("ago")
        assert load["numbers"] == [{"label": "Shipper BOL #", "value": "32950027"}]
        event = load["events"][0]
        assert event["telegramMessageIds"] == [100, 101] and event["messageIds"] == [100 << 20, 101 << 20] and event["stage"] == "Loaded"
        assert len(event["at"]) == 19 and event["at"][10] == " "  # Brain's local "YYYY-MM-DD HH:MM:SS", like the rest of the panel
        assert done["name"] == "Load 77001" and done["open"] is False and done["step"] == 8 and done["closedAt"]
        assert done["meta"][-1] == "Miles: about 300" and done["checks"] == []  # nothing is "not yet" on a closed load

        FakeBrain.state["noLoads"] = True  # a Brain from before loads: the rest of the panel still works
        older = (await browser.get("/v1/brain/chats/-5534970202/panel")).json()
        assert older["loads"] is None and older["items"][0]["runId"] == 6


def test_a_chat_without_a_job_that_follows_loads_has_no_loads_section():
    from foxygram.brain_loads import panel_loads
    assert panel_loads(BOARD, "-5534970202", ["job1"]) is None
    assert panel_loads(None, "-5534970202", ["job2"]) is None
    assert panel_loads({**BOARD, "loads": []}, "-5534970202", ["job2"]) == []
    assert [load["id"] for load in panel_loads(BOARD, "-100777", ["job2"])] == [10]


def test_load_times_read_as_ago():
    from datetime import datetime, timezone
    from foxygram.brain_loads import ago, local
    now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    assert ago("2026-11-11T11:59:30Z", now) == "just now"
    assert ago("2026-11-11T11:20:00Z", now) == "40 min ago"
    assert ago("2026-11-11T07:00:00Z", now) == "5 h ago"
    assert ago("2026-11-08T12:00:00Z", now) == "3 days ago"
    assert ago("", now) == "" and local("not a time") == ""


async def test_sending_can_be_switched_off_for_a_chat(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as browser:
        csrf = {"x-foxygram": "1"}
        await browser.post("/v1/brain/chats/-5534970202/jobs", json={"job_id": "job2", "on": True}, headers=csrf)
        assert (await browser.post("/v1/brain/chats/-5534970202/sending", json={"on": False})).status_code == 403
        done = (await browser.post("/v1/brain/chats/-5534970202/sending", json={"on": False}, headers=csrf)).json()
        assert done["chat"]["sending"] is False and done["text"]
        assert FakeBrain.seen[-1]["body"] == {"chatId": "-5534970202", "on": False}
        panel = (await browser.get("/v1/brain/chats/-5534970202/panel")).json()
        assert panel["sending"] is False and panel["jobs"][0]["id"] == "job2"  # still read, just never sent
        back = (await browser.post("/v1/brain/chats/-5534970202/sending", json={"on": True}, headers=csrf)).json()
        assert back["chat"]["sending"] is True
        assert (await browser.post("/v1/brain/chats/-5534970202/sending", json={}, headers=csrf)).status_code == 422
    assert all(asked["token"] == TOKEN for asked in FakeBrain.seen)


async def test_decisions_reach_brain_and_its_refusals_come_back(service, brain_url, brain_env):
    use_brain(service, brain_url, env_file=str(brain_env))
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as browser:
        csrf = {"x-foxygram": "1"}
        assert (await browser.post("/v1/brain/actions/3/decide", json={"decision": "approve"})).status_code == 403
        done = await browser.post("/v1/brain/actions/3/decide", json={"decision": "reject", "reason": "Уточни время"}, headers=csrf)
        assert done.json() == {"text": "#3 reject"}
        assert FakeBrain.seen[-1]["body"] == {"id": 3, "decision": "reject", "reason": "Уточни время"}
        refused = await browser.post("/v1/brain/actions/3/decide", json={"decision": "answer", "text": ""}, headers=csrf)
        assert refused.status_code == 400 and refused.json()["detail"] == "Write an answer first."
        unknown = await browser.post("/v1/brain/actions/3/decide", json={"decision": "send-everything"}, headers=csrf)
        assert unknown.status_code == 422
    assert all(asked["token"] == TOKEN for asked in FakeBrain.seen)


def test_brain_settings_have_safe_defaults(config):
    assert config.brain.url == "http://127.0.0.1:7777"
    assert config.brain.env_path.name == ".env" and config.brain.env_path.parent.name == "Brain"
    custom = replace(config.brain, env_file="D:/x/.env")
    assert str(custom.env_path).replace("\\", "/") == "D:/x/.env"
