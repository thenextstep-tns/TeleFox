from dataclasses import replace

import httpx
import pytest

from foxygram.admin import create_admin
from foxygram.analysis import IncomingRow, close_ready_bursts, process_burst, store_message
from foxygram.api import create_api
from foxygram.config import BurstConfig, CaseConfig, ClaudeConfig
from foxygram.db import now

from .conftest import add_chat

BURSTS = BurstConfig(quiet_seconds=60, max_seconds=300, max_messages=5)


@pytest.fixture
async def api(service):
    transport = httpx.ASGITransport(app=create_api(service))
    headers = {"Authorization": f"Bearer {service.config.secrets.api_token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://x", headers=headers) as client:
        yield client


@pytest.fixture
async def admin(service):
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as client:
        yield client


class Stub:
    config = ClaudeConfig()

    def __init__(self, title="Дело"):
        self.title = title

    async def run(self, *_):
        return {"intent": "request", "needs_reply": True, "urgency": "normal", "entities": [], "summary": "s",
                "case": {"action": "new", "case_id": None, "title": self.title, "confidence": 0.9, "case_summary": "cs"}}


async def make_case(service, chat_id=100, message_id=1, title="Дело"):
    add_chat(service, chat_id=chat_id)
    store_message(service.db, IncomingRow(chat_id, message_id, now(), 7, "А", False, "text", "нужен инвойс срочно", 0))
    close_ready_bursts(service.db, BURSTS, current=now() + 120)
    burst = service.db.scalar("SELECT id FROM bursts ORDER BY id DESC LIMIT 1")
    await process_burst(service.db, Stub(title), CaseConfig(), burst)
    return burst


async def test_every_route_requires_the_token(service):
    app = create_api(service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as client:
        for route in app.routes:
            for method in route.methods:
                path = route.path.replace("{chat_id}", "1").replace("{case_id}", "1").replace("{burst_id}", "1") \
                    .replace("{project_id}", "1").replace("{category_id}", "1")
                response = await client.request(method, path, json={}, params={"q": "x"})
                assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


async def test_wrong_token_rejected(service):
    transport = httpx.ASGITransport(app=create_api(service))
    async with httpx.AsyncClient(transport=transport, base_url="http://x", headers={"Authorization": "Bearer nope"}) as c:
        assert (await c.get("/v1/health")).status_code == 401


async def test_health(api):
    body = (await api.get("/v1/health")).json()
    assert body["claude"]["state"] == "ok"


async def test_phone_activity_is_visible(api, service):
    assert service.phone_seen_at == 0
    await api.get("/v1/health")
    assert service.phone_seen_at > 0


async def test_selecting_a_chat(api, service):
    add_chat(service, ai=False)
    assert (await api.patch("/v1/chats/100", json={"ai_enabled": True})).status_code == 200
    assert service.db.scalar("SELECT ai_enabled FROM chats WHERE chat_id = 100") == 1


async def test_unknown_chat_404(api):
    assert (await api.patch("/v1/chats/999", json={"ai_enabled": True})).status_code == 404


async def test_project_assignment_and_clear(api, service):
    add_chat(service, ai=False)
    project = (await api.post("/v1/projects", json={"name": "Авто"})).json()["id"]
    category = (await api.post(f"/v1/projects/{project}/categories", json={"name": "Клиент"})).json()["id"]
    await api.patch("/v1/chats/100", json={"project_id": project})
    await api.patch("/v1/chats/100", json={"category_id": category})
    flags = (await api.get("/v1/flags")).json()
    assert flags[0]["project_name"] == "Авто" and flags[0]["category_name"] == "Клиент"
    await api.patch("/v1/chats/100", json={"project_id": None})
    row = service.db.one("SELECT project_id, category_id FROM chats WHERE chat_id = 100")
    assert row == {"project_id": None, "category_id": None}


async def test_duplicate_project_conflicts(api):
    await api.post("/v1/projects", json={"name": "A"})
    assert (await api.post("/v1/projects", json={"name": "A"})).status_code == 409


async def test_case_list_detail_and_search(api, service):
    await make_case(service)
    cases = (await api.get("/v1/cases")).json()
    assert cases[0]["title"] == "Дело" and cases[0]["chats"][0]["chat_id"] == 100
    detail = (await api.get(f"/v1/cases/{cases[0]['id']}")).json()
    assert detail["timeline"][0]["summary"] == "s"
    assert detail["timeline"][0]["messages"][0]["text"] == "нужен инвойс срочно"
    found = (await api.get("/v1/search", params={"q": "инвойс"})).json()
    assert found[0]["chat_title"] == "Логистика"


async def test_search_survives_quotes(api):
    assert (await api.get("/v1/search", params={"q": '"'})).json() == []


async def test_close_and_reopen_case(api, service):
    await make_case(service)
    await api.patch("/v1/cases/1", json={"status": "closed"})
    assert (await api.get("/v1/cases")).json() == []
    assert len((await api.get("/v1/cases", params={"status": "closed"})).json()) == 1


async def test_merge(api, service):
    await make_case(service, title="A")
    await make_case(service, chat_id=200, message_id=2, title="B")
    assert (await api.post("/v1/cases/2/merge", json={"into": 1})).status_code == 200
    detail = (await api.get("/v1/cases/1")).json()
    assert len(detail["timeline"]) == 2
    assert (await api.get("/v1/cases/2")).status_code == 404


async def test_merge_into_itself_rejected(api, service):
    await make_case(service)
    assert (await api.post("/v1/cases/1/merge", json={"into": 1})).status_code == 400


async def test_move_records_a_correction(api, service):
    burst = await make_case(service, title="A")
    moved = (await api.post(f"/v1/bursts/{burst}/move", json={"new_title": "Другое дело"})).json()
    assert moved["case_id"] == 2
    row = service.db.one("SELECT from_case, to_case FROM corrections")
    assert row == {"from_case": "A", "to_case": "Другое дело"}


async def test_unlink_burst(api, service):
    burst = await make_case(service)
    assert (await api.post(f"/v1/bursts/{burst}/move", json={})).json()["case_id"] is None
    assert service.db.scalar("SELECT COUNT(*) FROM case_links") == 0


async def test_review_and_confirm(api, service):
    burst = await make_case(service)
    service.db.execute("UPDATE case_links SET needs_review = 1")
    assert len((await api.get("/v1/review")).json()) == 1
    await api.post(f"/v1/bursts/{burst}/confirm")
    assert (await api.get("/v1/review")).json() == []


async def test_admin_page_loads(admin):
    assert "FoxyGram" in (await admin.get("/")).text


async def test_pairing_qr_is_a_standalone_image(admin, service):
    service.config = replace(service.config, server=replace(service.config.server, public_url="https://x.example"))
    response = await admin.get("/api/qr/pair.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert 'xmlns="http://www.w3.org/2000/svg"' in response.text


async def test_admin_rejects_foreign_host(service):
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url="http://evil.example") as client:
        assert (await client.get("/api/state")).status_code == 403


async def test_admin_post_needs_csrf_header(admin):
    assert (await admin.post("/api/login/qr")).status_code == 403


async def test_admin_rejects_cross_origin_post(admin):
    response = await admin.post("/api/login/qr", headers={"x-foxygram": "1", "origin": "https://evil.example"})
    assert response.status_code == 403


async def test_admin_toggle(admin, service):
    add_chat(service, ai=False)
    response = await admin.post("/api/chats/100/ai", json={"enabled": True}, headers={"x-foxygram": "1"})
    assert response.status_code == 200
    assert service.db.scalar("SELECT ai_enabled FROM chats WHERE chat_id = 100") == 1
