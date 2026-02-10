# bishop-meta (WhatsApp Bot)

This folder contains the WhatsApp webhook entrypoints and notes for BishopBot.

## What It Does

- Receives WhatsApp messages (Meta WhatsApp Cloud API webhook)
- Enqueues the same Redis jobs that Slack uses (`local_worker.process_task` and `local_worker.process_terminal_input`)
- Streams back verbose terminal output over WhatsApp

## Key Commands (WhatsApp)

- Send any text: starts a new `/cli` Gemini session (yolo by default via `GEMINI_CLI_ARGS`)
- `!enter [session_id]`: send Enter
- `!n [session_id]`: send "n"
- `!y [session_id]`: send "y"
- `!status [session_id]`: request an immediate output snapshot
- `!stop [session_id]`: stop polling for that session
- `!send <session_id> <text>`: send arbitrary text to an existing session

If `[session_id]` is omitted, the bot uses your most recent session (stored in Redis for 24h).

## Env Vars

Required for WhatsApp:

- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`

Optional hardening:

- `WHATSAPP_APP_SECRET` (enables webhook signature verification)

Tuning:

- `TERMINAL_BOOT_DELAY_SECONDS` (default 7)
- `TERMINAL_POLL_INTERVAL_SECONDS` (default 40)
- `TERMINAL_TAIL_LINES_WHATSAPP` (default 40)

## Webhook Paths

- `GET /whatsapp/webhook` (verification)
- `POST /whatsapp/webhook` (message events)

Health check:

- `GET /` -> `OK`
