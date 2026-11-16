"""The browser app on the public address, behind a Google sign-in.

The phone keeps its pairing token. A browser signs in with Google through Brain's Firebase project: Brain hands out
the project's public web config and checks Firebase's signed answer, so this server needs neither. Only the emails in
[web] allowed_emails get a session: a cookie that goes back only over https to this address. Every browser route then
needs that session, and writes also need the page's own header and this address as their origin, so no other website
can use a signed-in browser. With allowed_emails empty, the public address serves the phone only, as before.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from .brain import BrainError
from .service import Service

COOKIE = "fg_session"
SESSION_DAYS = 30
CSRF_HEADER = "x-foxygram"
SCHEMA = """CREATE TABLE IF NOT EXISTS web_sessions(
  token_hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
)"""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WebAuth:
    """Who is signed in to the browser app on the public address."""

    def __init__(self, service: Service):
        self.service = service
        service.db.execute(SCHEMA)

    @property
    def allowed(self) -> set[str]:
        return set(self.service.config.web.allowed_emails)

    @property
    def enabled(self) -> bool:
        return bool(self.allowed) and bool(self.service.config.server.public_url)

    @property
    def origin(self) -> str:
        parts = urlsplit(self.service.config.server.public_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def secure(self) -> bool:
        return self.origin.startswith("https://")

    def start(self, email: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        self.service.db.execute("DELETE FROM web_sessions WHERE expires_at < ?", (now.isoformat(),))
        self.service.db.execute(
            "INSERT INTO web_sessions(token_hash, email, created_at, expires_at) VALUES(?,?,?,?)",
            (_hash(token), email, now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat()))
        return token

    def email_of(self, request: Request) -> str | None:
        """The signed-in email, while the session lasts and the email is still allowed."""
        token = request.cookies.get(COOKIE, "")
        if not token:
            return None
        row = self.service.db.one("SELECT email, expires_at FROM web_sessions WHERE token_hash = ?", (_hash(token),))
        if row is None or row["expires_at"] < _now().isoformat() or row["email"] not in self.allowed:
            return None
        return row["email"]

    def end(self, request: Request) -> None:
        token = request.cookies.get(COOKIE, "")
        if token:
            self.service.db.execute("DELETE FROM web_sessions WHERE token_hash = ?", (_hash(token),))

    def check_write(self, request: Request) -> None:
        """A write from a signed-in browser must come from this app's own page."""
        if request.method in ("GET", "HEAD"):
            return
        origin = request.headers.get("origin")
        site = request.headers.get("sec-fetch-site")
        if request.headers.get(CSRF_HEADER) != "1" or (origin and origin != self.origin) or (site and site not in ("same-origin", "none")):
            raise HTTPException(status_code=403, detail="forbidden")

    def require(self, request: Request) -> str:
        """A browser route: a signed-in, allowed person; writes from this app's page only."""
        email = self.email_of(request)
        if email is None:
            raise HTTPException(status_code=401, detail="sign in first")
        self.check_write(request)
        return email

    def cookie(self, response: Any, token: str) -> None:
        response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, secure=self.secure, samesite="lax", path="/")


class GoogleSignIn(BaseModel):
    idToken: str


def add_web_signin(app: FastAPI, service: Service, auth: WebAuth, page_html: str, page_headers: dict[str, str]) -> None:
    """The sign-in page, signing in and out, and the app's page behind them. Registered before the app's own routes."""

    def not_here() -> None:
        if not auth.enabled:
            raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/", include_in_schema=False)
    async def root(request: Request) -> RedirectResponse:
        not_here()
        return RedirectResponse("/app" if auth.email_of(request) else "/signin", status_code=302)

    @app.get("/app", include_in_schema=False)
    async def app_page(request: Request):
        not_here()
        if not auth.email_of(request):
            return RedirectResponse("/signin", status_code=302)
        return HTMLResponse(page_html, headers=page_headers)

    @app.get("/signin", include_in_schema=False)
    async def signin(request: Request) -> HTMLResponse:
        not_here()
        if auth.email_of(request):
            return RedirectResponse("/app", status_code=302)  # type: ignore[return-value]
        try:
            fb = await service.brain.firebase()
        except BrainError as error:
            return _page(None, f"Brain can't help with signing in right now: {error.message}")
        config = fb.get("config")
        if not config:
            return _page(None, "Google sign-in isn't set up in Brain yet (Brain's Team tab).")
        return _page(config, "")

    @app.post("/auth/google", include_in_schema=False)
    async def google(request: Request) -> JSONResponse:
        not_here()
        auth.check_write(request)
        try:
            body = GoogleSignIn(**(await request.json()))
        except Exception as error:
            raise HTTPException(status_code=400, detail="Send the Google sign-in.") from error
        try:
            who = await service.brain.verify_firebase(body.idToken)
        except BrainError as error:
            raise HTTPException(status_code=400 if error.status < 500 else 503, detail=error.message) from error
        email = str(who.get("email", "")).strip().lower()
        if not email or not who.get("emailVerified"):
            raise HTTPException(status_code=403, detail="That Google account has no confirmed email.")
        if email not in auth.allowed:
            raise HTTPException(status_code=403, detail=f"{email} may not open FoxyGram here.")
        response = JSONResponse({"ok": True, "email": email})
        auth.cookie(response, auth.start(email))
        return response

    @app.post("/auth/signout", include_in_schema=False)
    async def signout(request: Request) -> JSONResponse:
        not_here()
        auth.check_write(request)
        auth.end(request)
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response


def token_or_session(service: Service, auth: WebAuth):
    """The phone's pairing token, or a signed-in browser (the browser app shares the phone's /v1 routes)."""
    expected = service.config.secrets.api_token

    async def guard(request: Request, authorization: str = Header(default="")) -> None:
        supplied = authorization.removeprefix("Bearer ").strip()
        if supplied and hmac.compare_digest(supplied.encode(), expected.encode()):
            from .db import now
            service.phone_seen_at = now()
            return
        if auth.enabled and auth.email_of(request):
            auth.check_write(request)
            return
        raise HTTPException(status_code=401, detail="invalid token")

    return guard


def _page(config: dict[str, Any] | None, problem: str) -> HTMLResponse:
    auth_domain = (config or {}).get("authDomain", "")
    csp = ("default-src 'none'; script-src 'unsafe-inline' https://www.gstatic.com/firebasejs/ https://apis.google.com; "
           "connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.googleapis.com; "
           f"frame-src {'https://' + auth_domain + ' ' if auth_domain else ''}https://accounts.google.com; style-src 'unsafe-inline'; "
           "img-src 'self' data: https:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
    # Into the script as JSON, with "<" escaped so nothing in it can close the script.
    data = json.dumps({"config": config, "problem": problem}).replace("<", "\\u003c")
    return HTMLResponse(SIGNIN_PAGE.replace("__DATA__", data), headers={
        "Cache-Control": "no-store", "Content-Security-Policy": csp, "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
    })


SIGNIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in to FoxyGram</title>
<style>
  :root { color-scheme: light dark; --bg: #f6f6f4; --panel: #fff; --text: #1d1d1b; --muted: #6b6b66; --line: #e3e3de; --err: #a1261b; }
  @media (prefers-color-scheme: dark) { :root { --bg: #161615; --panel: #1f1f1d; --text: #ececea; --muted: #a3a39d; --line: #33332f; --err: #ff8a7a; } }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--text);
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { width: min(380px, calc(100vw - 32px)); background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 24px; }
  h1 { font-size: 20px; margin: 0 0 6px; }
  p { margin: 0 0 16px; color: var(--muted); }
  button { width: 100%; font: inherit; font-weight: 600; padding: 10px; border-radius: 8px; border: 1px solid var(--line);
           background: var(--panel); color: var(--text); cursor: pointer; }
  button:disabled { opacity: .6; cursor: default; }
  .err { color: var(--err); margin: 12px 0 0; }
</style></head>
<body><main>
  <h1>FoxyGram</h1>
  <p>Sign in with the Google account FoxyGram knows. You stay signed in on this browser for 30 days.</p>
  <button id="google" type="button" disabled>Continue with Google</button>
  <p class="err" id="err" hidden></p>
</main>
<script>
(function () {
  var DATA = __DATA__;
  var err = document.getElementById('err'), btn = document.getElementById('google');
  function fail(t) { err.textContent = t; err.hidden = false; btn.disabled = false; }
  if (DATA.problem) { fail(DATA.problem); btn.disabled = true; return; }
  var SDK = 'https://www.gstatic.com/firebasejs/10.14.1/';
  function load(src) { return new Promise(function (ok, no) { var s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); }); }
  var auth = null;
  load(SDK + 'firebase-app-compat.js').then(function () { return load(SDK + 'firebase-auth-compat.js'); }).then(function () {
    firebase.initializeApp(DATA.config);
    auth = firebase.auth();
    return auth.setPersistence(firebase.auth.Auth.Persistence.NONE);
  }).then(function () { btn.disabled = false; }, function () { fail('Google sign-in didn\\'t load. Check the internet connection.'); });
  btn.addEventListener('click', function () {
    if (!auth) return;
    btn.disabled = true; err.hidden = true;
    auth.signInWithPopup(new firebase.auth.GoogleAuthProvider()).then(function (r) { return r.user.getIdToken(); }).then(function (idToken) {
      return fetch('/auth/google', { method: 'POST', headers: { 'content-type': 'application/json', 'x-foxygram': '1' }, body: JSON.stringify({ idToken: idToken }) });
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); }).then(function (x) {
      if (auth) auth.signOut().catch(function () {});
      if (!x.ok) { fail(x.j && x.j.detail ? x.j.detail : 'That didn\\'t work. Try again.'); return; }
      location.href = '/app';
    }, function (e) {
      var c = e && e.code || '';
      fail(c === 'auth/popup-closed-by-user' ? 'The Google window was closed. Try again.'
        : c === 'auth/unauthorized-domain' ? 'Firebase doesn\\'t allow ' + location.hostname + ' yet (Authorized domains in the Firebase console).'
        : c === 'auth/popup-blocked' ? 'The browser blocked Google\\'s window. Allow pop-ups for this page.'
        : 'Signing in didn\\'t work' + (c ? ' (' + c + ')' : '') + '. Try again.');
    });
  });
})();
</script>
</body></html>
"""
