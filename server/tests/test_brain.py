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
                "jobs": jobs["jobs"], "viaFolder": ["job2"], "added": jobs["added"], "removed": []}

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
    asked = [a["path"] for a in FakeBrain.seen]
    assert any(p.startswith("/brain/api/chat-analysis?chatId=-5534970202") for p in asked)


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
