# FoxyGram architecture

FoxyGram has two independent parts. The phone is a complete Telegram client and works
without the server. The server adds the part a phone should not do: reading selected
chats all day, asking Claude what they mean, and tying related conversations together.

```
 Telegram <── MTProto ──> Android app (TDLib)      chats, media, alerts, replies
 Telegram <── MTProto ──> Windows server (TDLib)   selected chats only
                                │
                                ├── claude -p      intent and topic, on the owner's plan
                                ├── SQLite         messages, bursts, cases
                                └── HTTPS tunnel ──> Android app   cases, flags, review
```

Each side logs in to Telegram as its own device. The app talks to Telegram directly, so a
server outage costs the case tracker and nothing else.

## Android app

Kotlin and Jetpack Compose on TDLib, built by this repo's CI from the commit pinned in
`tdlib.version`. The UI maps `TdApi` objects into plain models (`td/TdMapper.kt`), so
screens and screenshot tests never touch TDLib.

- **Message order.** `td/ChatSession.kt` keeps one sorted window per chat and applies
  TDLib updates to it. `model/Feed.kt` turns the window into rows: date separators, sender
  groups, albums, the unread marker.
- **Chat order.** Taken from TDLib's own chat positions per list, which is also how
  Telegram folders, pinning and the archive work.
- **Media.** `TdFiles` serves images and files. `TdDataSource` lets Media3 play voice and
  video while they download.

### Alerts without Firebase

`notify/Background.kt` runs a foreground service that keeps TDLib's one socket open, and
alerts are raised from `updateNewMessage` through `shouldAlert` (`notify/Alerts.kt`).
Nothing polls, and no third party sits in the delivery path.

The cost is the keep-alive. While the app is in the background, TDLib pings about once
every 1–2 minutes, so the radio wakes that often. The real battery figure has to be
measured on the phone.

The app plays the alert sound itself and posts to a silent channel, because some vendors
mute third-party channel sounds.

Each folder, and the archive, can alert on everything, on mentions only or not at all, with
its own sound. A chat in several folders follows the loudest setting. The archive is off by
default.

## Server

Python 3.12, FastAPI and SQLite (WAL, FTS5). It ships as a PyInstaller zip and starts from
a Scheduled Task at logon. Settings live in `%LOCALAPPDATA%\FoxyGram\config.toml`.

| Port | Bound to | Purpose | Protection |
|------|----------|---------|------------|
| 8787 | tunnel | phone API | bearer token |
| 8788 | 127.0.0.1 | admin page, browser client | Host allowlist, CSRF header, same-origin check |

The phone reaches port 8787 through a Cloudflare tunnel the server keeps running: a named
tunnel for a fixed address, or a free quick tunnel whose address changes on restart. The
server always gives `cloudflared` its own config, so another tunnel on the same machine
can't take over its routing.

### Browser client

`http://127.0.0.1:8788/app` copies the phone app's screens for the laptop: chat list with
folders and archive, chats with replies, photos, files and voice, cases, the review queue and
the Claude chat list. It is only reachable from this computer, and the tunnel never sees it.

Unlike the phone, it has no Telegram session of its own. It reads and sends through the
server's session (`web.py`), which keeps a copy of TDLib's chats, users and folders
(`telegram/store.py`) and maps messages the way `td/TdMapper.kt` does (`web_model.py`).
Changes reach open tabs over one event stream as "reload this" hints, merged per chat.
Sent messages come from the "FoxyGram Server" device. The server marks nothing read on its
own; the browser does, for messages shown in a chat that is open in a focused tab, and a
setting turns that off. Files are downloaded by TDLib on request and served only from its
folder. Anything a browser could run, such as SVG, is served as a download.

The cases, labels and review screens call the same `/v1` routes as the phone. On this port
they are guarded by the control page's checks instead of the token.

### Pipeline

Only chats the owner selects are stored. Everything else is dropped on arrival.

1. **Entities.** Regexes pull out VINs, ISO 6346 containers (check digit verified), phone
   numbers and invoice numbers.
2. **Bursts.** Messages group into a burst, which closes on quiet time, age or size.
3. **Filter.** `worth_analysing` skips trivial bursts without a model call.
4. **Candidates.** Open cases sharing an entity, the chat's recent cases, and full-text
   matches.
5. **Claude.** One call per burst returns intent and the case decision as schema-checked
   JSON.
6. **Guards.** A single open case sharing a VIN or container always wins. Case ids the
   model invents are ignored. Low confidence goes to the review queue. Corrections are fed
   back as examples.

Replying in a chat clears its "needs reply" flag without using the model.

### Claude

The server runs the native `claude` binary in print mode, so usage counts against the
owner's plan and no API key exists anywhere. The binary gets no tools, no MCP servers, no
settings and an empty working directory, and message text is passed only over stdin. That
matters because chat content is untrusted input.

Calls are capped per hour and per day, and analysis pauses on quota or login errors. The
model is set by `model` in `config.toml`.

## Pairing and secrets

The repository and the public APK contain no Telegram credentials. The server's admin page
shows a `foxygram://pair` QR code holding the server URL, the bearer token, `api_id` and
`api_hash`. The app stores them locally after scanning.

## Releases

Push to `foxygram` triggers `.github/workflows/android.yml` and `server.yml`, which publish
tags `foxygram-v0.1.N` and `foxygram-server-v0.1.N`. They are prereleases, so they never
become the repository's `latest`, and `update/AppUpdater.kt` picks releases by tag prefix.

## Not built

Native calls (they need Telegram's VoIP stack), voice transcription, local embeddings,
digests, reply drafts, GIF autoplay, WebM stickers, and update checks on
launch (button only).

## Building

```bash
cd server && uv run --python 3.12 pytest -q
```

```bash
cd android && ./gradlew testDebugUnitTest assembleRelease
```

Gradle downloads and checksums TDLib from the release named after `tdlib.version`.
