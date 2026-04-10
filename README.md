# Slack-Integrated Multi-Agent CLI Shell

This tool lets you drive your local development environment from Slack using natural language, with runtime-aware terminal sessions for Gemini and Codex.

## Features
- **NL to Code**: Uses Gemini 1.5 Pro to translate English commands into Bash or Python.
- **Auto-Git**: Automatically commits changes to your repository after each command.
- **Verbose Logging**: Detailed execution logs stored in `logs/`, including per-session runtime transcripts in `logs/sessions/`.
- **Durable runtime heartbeat**: each Gemini/Codex session writes a lightweight state sidecar so the listener can reconcile fast terminal closes and short-lived Codex runs instead of guessing from the visible window alone.
- **Durable raw runtime capture**: each session also tees the underlying Gemini/Codex terminal stream into `logs/session-output/`, giving the poller a fallback source of truth when Terminal visibility drops or fast Codex runs finish before the visible window can be tailed.
- **Async Execution**: Handles long-running commands without timing out Slack.
- **YOLO automation**: Gemini launches with `--yolo` and executes the generated plan atomically so you can build, test, and push without manual prompts.
- **Real Codex runtime**: `/codex` now launches the actual Codex CLI in its own terminal session using configurable full-auto / yolo-style flags.
- **Runtime-native prompt delivery**: adapters can either open an interactive shell and type the prompt (`stdin`) or pass the prompt directly on launch (`argv`) for CLIs like `codex exec --full-auto`.
- **Runtime adapter architecture**: Gemini and Codex share the same session manager, polling loop, and controls through a runtime adapter layer instead of hardcoded Gemini launch logic.
- **Task planning**: Each slash command produces a numbered task list that is posted back to Slack before execution; the selected CLI runs each step sequentially and reports progress.

## Setup Instructions

1. **Clone the Repository**
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   - Copy `.env.example` to `.env`.
   - Fill in your `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN` (for Socket Mode), and `GEMINI_API_KEY`.
   - (Optional) Set `GEMINI_CLI_ARGS_YOLO`, `CODEX_CLI_ARGS_FULL_AUTO`, and `CODEX_CLI_ARGS_YOLO` to control the named launch modes for each runtime. Gemini defaults to `--yolo`; Codex defaults to `exec --full-auto` for `full-auto` mode and `--yolo` for `yolo` shell mode.
   - (Optional) Set `GEMINI_PROMPT_TRANSPORT` / `CODEX_PROMPT_TRANSPORT` to `stdin` or `argv` if you want to override how prompts are delivered to each runtime.
   - (Optional) Tune `GEMINI_BOOT_DELAY_SECONDS` and `CODEX_BOOT_DELAY_SECONDS` separately if one runtime needs more time to become interactive.
   - (Optional) Tune `TERMINAL_STATE_HEARTBEAT_SECONDS` / `TERMINAL_STATE_HEARTBEAT_STALE_SECONDS` if you want the runtime sidecar heartbeat to update faster or tolerate longer Terminal-visibility gaps.
   - (Optional) Set `SESSION_LOG_DIR`, `SESSION_STATE_DIR`, or `SESSION_OUTPUT_DIR` if you want runtime transcripts, lifecycle sidecars, or raw terminal captures written somewhere other than the default `logs/` paths.
4. **Run the App**:
   ```bash
   python app.py
   ```
5. **Optional local smoke validation** (uses the real listener + session manager without Slack):
   ```bash
   python scripts/run_listener_smoke.py /codex --full-auto "inspect the repo and summarize what you see"
   python scripts/run_listener_smoke.py /codex --yolo "inspect the auth flow and summarize blockers"
   python scripts/run_listener_smoke.py /cli runtime:codex --yolo "inspect the listener tests"
   ```
6. **Slack Configuration**:
   - Create a Slack App at `api.slack.com`.
   - Enable **Socket Mode**.
   - Under **Slash Commands**, create `/cli` and `/codex`.
   - Install the app to your workspace.

## Usage
In Slack, run either `/cli` or `/codex` followed by a request. You can optionally prefix the request with a runtime selector (`runtime:codex`, `runtime:gemini`, `--codex`, `--gemini`) and/or a launch-mode selector such as `--yolo`, `--full-auto`, or `mode:yolo`.

```
/cli open the project folder, run the tests, bump the version, and push the tag
/codex scaffold a new Next.js API route that returns the current timestamp and document it
/codex --yolo inspect the auth flow, patch the failing test, and summarize what changed
/cli runtime:codex --yolo inspect the auth flow, patch the failing test, and summarize what changed
/cli --codex fix the flaky listener test and leave Gemini as the default when no runtime override is present
```

The bot now:
1. Refines your request with GPT-4o.
2. Builds a numbered task list, posts it back to Slack, and starts the correct runtime for the slash command.
3. Gemini or Codex launches in the selected runtime mode (for example Gemini `--yolo`, Codex `exec --full-auto`, or Codex `--yolo` shell mode), executes each task sequentially, runs `git status`, commits, and pushes any changes.
4. You receive periodic updates every 40 seconds plus a session summary when the work completes, with the runtime clearly labeled in status headers.
5. Every session also writes a durable markdown transcript with metadata, tailed updates, and completion/failure notes so Gemini and Codex runs can be audited after the chat scrolls away.
6. Each session also writes a raw runtime-output capture that the poller can parse if Terminal closes, scrolls past the important markers, or never exposes the full buffer in time.
7. The same listener updates can also be routed to `console:<label>` targets during local smoke runs, which gives Gemini/Codex mode validation without needing a live Slack round trip.
