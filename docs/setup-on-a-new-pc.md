# Setting up the FoxyGram server on a new Windows PC

Written for a Claude Code session running on the new PC, and readable by a person. Read
[architecture.md](architecture.md) first for how the pieces fit.

## What already exists

- The Cloudflare tunnel `foxygram` and the DNS record `tlg.dodobot.me`. The record points at
  the tunnel, not at a computer, so **DNS does not change when the server moves**.
- Published builds of the server and the phone app, as GitHub releases tagged
  `foxygram-server-v*` and `foxygram-v*`.

The server has never been signed in to Telegram, so there is no session to migrate.

## Rules

- This repository is public. Never commit `config.toml`, `tunnel.json`, `secrets.json`,
  Telegram's `api_id` / `api_hash`, or anything from `%LOCALAPPDATA%\FoxyGram`.
- Only one PC may run this server. A second copy would share the tunnel and receive half the
  phone's requests.
- Don't enter the owner's Telegram or Cloudflare credentials yourself. Ask them to do it.
- Registering the startup task is the owner's call. Let them run `install.cmd`, or get their
  explicit go-ahead first.

## Steps

### 1. Install cloudflared

```bash
winget install --id Cloudflare.cloudflared
```

### 2. Get the server

Download `FoxyGram-Server-Windows.zip` from the newest `foxygram-server-v*` release. These are
prereleases, so list releases and filter by tag instead of using `releases/latest`, which
belongs to a different app. Unzip it somewhere permanent, for example
`%LOCALAPPDATA%\Programs`.

### 3. Fill the data folder

The data folder is `%LOCALAPPDATA%\FoxyGram`. Use whichever applies.

**If the owner has `FoxyGram-move.zip`:** unzip `config.toml` and `tunnel.json` into the data
folder. Nothing else is needed.

**If not:**

1. Have the owner run this and choose **dodobot.me** on the page that opens:
   ```bash
   cloudflared tunnel login
   ```
2. Write the tunnel credentials for the existing tunnel. Don't create a new tunnel:
   ```bash
   cloudflared tunnel token --cred-file "%LOCALAPPDATA%\FoxyGram\tunnel.json" foxygram
   ```
3. Get the tunnel's id from `cloudflared tunnel list`.
4. Ask the owner for Telegram's `api_id` and `api_hash`, which come from
   <https://my.telegram.org>. Don't print them back.
5. Start the server once to generate `config.toml`, stop it, then set:
   ```toml
   [telegram]
   api_id = 12345678
   api_hash = "..."

   [server]
   public_url = "https://tlg.dodobot.me"

   [tunnel]
   mode = "named"
   tunnel_id = "<id from step 3>"
   credentials_file = "tunnel.json"
   ```
   A relative `credentials_file` is resolved against the data folder.

### 4. Install

The owner runs `install.cmd` from the unzipped folder. It registers a startup task and opens
the control page at `http://127.0.0.1:8788`.

### 5. Check it

`https://tlg.dodobot.me/v1/health` must answer **401** without a token. That means the request
reached this server. A 502 or 530 means the tunnel isn't connected: look in
`%LOCALAPPDATA%\FoxyGram\logs\server.log`. If it says `cloudflared not found`, restart the PC
or set the full path in `[tunnel] cloudflared`.

### 6. The owner finishes

1. Sign in to Telegram on the control page. The code usually arrives as a message inside
   another logged-in Telegram client, not by SMS.
2. Log in Claude on this PC with `claude auth login`. Analysis does nothing until then.
3. Install the phone app and scan the pairing code on the control page.
4. Pick the chats to analyse.
5. Stop this laptop from sleeping on mains power, including when the lid is closed. The
   server is unreachable while it sleeps.

## If Telegram asks for payment to log in

The app and the control page say so and offer QR login, which needs another logged-in client
to approve it. If none is available, add a way to approve the login from an existing session.
With Telethon that is `functions.auth.AcceptLoginTokenRequest`.

## Conventions for further work

Commit on the `foxygram` branch. Pushing there triggers the app and server builds. Keep
releases as `--prerelease --latest=false`, so they never become the repository's `latest`.
