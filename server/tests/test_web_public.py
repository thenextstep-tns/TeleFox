"""The browser app on the public address, behind a Google sign-in that Brain checks.

Brain is faked: it says whose a sign-in is. Only the emails in [web] allowed_emails get a session, the cookie works
only over https on this address, and writes need the page's own header and this address as origin. The phone's token
keeps working as before."""
from dataclasses import replace

import httpx
import pytest

from foxygram.api import create_api
from foxygram.brain import BrainError
from foxygram.config import ServerConfig, WebConfig
from foxygram.service import Service
from foxygram.telegram.session import TelegramSession

from .conftest import FakeClient

ORIGIN = "https://tlg.example.test"
OWNER = "owner@example.com"


class FakeBrain:
    """Brain's two answers: the Firebase web config, and whose a sign-in is."""

    def __init__(self):
        self.who = {"good-token": {"email": OWNER, "emailVerified": True},
                    "stranger": {"email": "someone@example.com", "emailVerified": True},
                    "unconfirmed": {"email": OWNER, "emailVerified": False}}

    async def firebase(self):
        return {"config": {"apiKey": "AIza-test", "authDomain": "demo.firebaseapp.com", "projectId": "demo-brain", "appId": "1:1:web:1"}}

    async def verify_firebase(self, id_token):
        if id_token not in self.who:
            raise BrainError(400, "That isn't a Firebase sign-in.")
        return self.who[id_token]


async def make_service(config, allowed=(OWNER,)):
    cfg = replace(config, server=replace(ServerConfig(), public_url=ORIGIN), web=WebConfig(allowed_emails=allowed))
    svc = Service(cfg, session=TelegramSession(cfg, client_factory=FakeClient))
    svc.brain = FakeBrain()
    return svc


@pytest.fixture
async def public(config):
    svc = await make_service(config)
    transport = httpx.ASGITransport(app=create_api(svc))
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        client.service = svc
        yield client
    svc.stop.set()
    svc.db.close()


async def sign_in(client, token="good-token"):
    return await client.post("/auth/google", json={"idToken": token}, headers={"x-foxygram": "1", "origin": ORIGIN})


async def test_without_allowed_emails_the_public_address_is_the_phones_only(config):
    svc = await make_service(config, allowed=())
    transport = httpx.ASGITransport(app=create_api(svc))
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        assert (await client.get("/app")).status_code == 404
        assert (await client.get("/signin")).status_code == 404
        assert (await client.get("/app/api/state")).status_code == 404
        assert (await client.get("/v1/health")).status_code == 401
        token = {"Authorization": f"Bearer {svc.config.secrets.api_token}"}
        assert (await client.get("/v1/health", headers=token)).status_code == 200
    svc.stop.set()
    svc.db.close()


async def test_the_app_sends_you_to_sign_in_first(public):
    r = await public.get("/app")
    assert r.status_code == 302 and r.headers["location"] == "/signin"
    assert (await public.get("/")).headers["location"] == "/signin"
    page = await public.get("/signin")
    assert page.status_code == 200 and '"projectId": "demo-brain"' in page.text
    assert "https://www.gstatic.com/firebasejs/" in page.headers["content-security-policy"]
    assert "frame-src https://demo.firebaseapp.com" in page.headers["content-security-policy"]
    assert (await public.get("/app/api/state")).status_code == 401
    assert (await public.get("/v1/health")).status_code == 401


async def test_only_an_allowed_confirmed_google_account_gets_in(public):
    no_header = await public.post("/auth/google", json={"idToken": "good-token"})
    assert no_header.status_code == 403
    other_site = await public.post("/auth/google", json={"idToken": "good-token"}, headers={"x-foxygram": "1", "origin": "https://evil.test"})
    assert other_site.status_code == 403
    stranger = await sign_in(public, "stranger")
    assert stranger.status_code == 403 and "may not open FoxyGram" in stranger.json()["detail"]
    unconfirmed = await sign_in(public, "unconfirmed")
    assert unconfirmed.status_code == 403
    fake = await sign_in(public, "made-up")
    assert fake.status_code == 400
    assert "fg_session" not in public.cookies


async def test_signed_in_the_app_works_and_writes_come_only_from_its_page(public):
    r = await sign_in(public)
    assert r.status_code == 200 and r.json()["email"] == OWNER
    cookie = r.headers["set-cookie"]
    assert "fg_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "samesite=lax" in cookie.lower()
    page = await public.get("/app")
    assert page.status_code == 200 and "default-src 'self'" in page.headers["content-security-policy"]
    assert (await public.get("/")).headers["location"] == "/app"
    assert (await public.get("/v1/health")).status_code == 200
    # A write needs the page's header and this address; anything else is another website using the browser.
    no_header = await public.post("/app/api/chats/1/read", json={})
    assert no_header.status_code == 403
    other = await public.post("/app/api/chats/1/read", json={}, headers={"x-foxygram": "1", "origin": "https://evil.test"})
    assert other.status_code == 403
    cross = await public.post("/v1/brain/feedback", json={"text": "x"}, headers={"x-foxygram": "1", "sec-fetch-site": "cross-site"})
    assert cross.status_code == 403
    mine = await public.post("/app/api/chats/1/read", json={}, headers={"x-foxygram": "1", "origin": ORIGIN})
    assert mine.status_code not in (401, 403)


async def test_signing_out_ends_the_session(public):
    await sign_in(public)
    out = await public.post("/auth/signout", headers={"x-foxygram": "1", "origin": ORIGIN})
    assert out.status_code == 200
    public.cookies.clear()
    assert (await public.get("/app")).status_code == 302


async def test_the_phone_token_still_works_beside_the_browser(public):
    token = {"Authorization": f"Bearer {public.service.config.secrets.api_token}"}
    assert (await public.get("/v1/health", headers=token)).status_code == 200
    assert (await public.get("/v1/health", headers={"Authorization": "Bearer wrong"})).status_code == 401


async def test_an_email_taken_off_the_list_is_signed_out(config):
    svc = await make_service(config)
    transport = httpx.ASGITransport(app=create_api(svc))
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        assert (await sign_in(client)).status_code == 200
        svc.config = replace(svc.config, web=WebConfig(allowed_emails=("other@example.com",)))
        assert (await client.get("/app")).status_code == 302
    svc.stop.set()
    svc.db.close()
