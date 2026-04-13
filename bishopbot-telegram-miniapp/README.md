# BishopBot Telegram Mini App

A compact Telegram Mini App for BishopBot.

What it does:
- shows live BishopBot overview + session counts
- lists recent sessions
- lets you send `/cli` or `/codex` commands
- lets you send follow-up input to an active session
- supports Telegram initData auth, with optional browser fallback token for local testing

## Folder layout

- `index.html` — single-file mini app UI
- `.env.example` — required env vars for the BishopBot gateway

## Install

1. Keep this folder inside the BishopBot repo:
   - `BishopBot/bishopbot-telegram-miniapp`

2. Set env vars in BishopBot's `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_OWNER_ID=1992876655
TELEGRAM_ALLOWED_USERS=1992876655
TELEGRAM_MINIAPP_DIR=/Users/matthewbishop/BishopBot/bishopbot-telegram-miniapp
TELEGRAM_MINIAPP_TITLE=BishopBot Terminal
```

3. Point Telegram WebApp traffic at the BishopBot gateway URL.

4. In BotFather, set the mini app URL to:

```text
https://your-domain/miniapp/index.html
```

## Notes

- The frontend sends `X-Telegram-Init-Data` automatically when opened inside Telegram.
- For browser testing, the BishopBot server can also accept a Bearer token fallback.
- The BishopBot gateway needs a `/miniapp` static route plus `/api/miniapp/*` endpoints. That is the next implementation step.
