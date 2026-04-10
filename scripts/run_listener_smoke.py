#!/usr/bin/env python3
"""Run the real BishopBot listener flow locally against Gemini or Codex.

Examples:
  python scripts/run_listener_smoke.py /codex --full-auto "print the repo root"
  python scripts/run_listener_smoke.py /codex --yolo "inspect README and summarize"
  python scripts/run_listener_smoke.py /cli runtime:codex --yolo "inspect tests"
  python scripts/run_listener_smoke.py /cli "inspect the current repo"
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from handlers import cli_handler
from services.terminal_session_manager import SESSIONS, TerminalSessionManager


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BishopBot's real listener path locally.")
    parser.add_argument("command", choices=["/cli", "/codex"], help="Listener command surface to exercise")
    parser.add_argument("prompt", nargs="+", help="Prompt text and any runtime/mode flags to pass through unchanged")
    parser.add_argument("--user", default="local-smoke", help="Synthetic local user id")
    parser.add_argument("--target", default="console:smoke", help="Reply target (default: console:smoke)")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds to wait before bailing out")
    parser.add_argument("--poll", type=int, default=5, help="Seconds between local status checks")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_text = " ".join(args.prompt).strip()
    mode = "codex" if args.command == "/codex" else "gemini"

    print(f"🚦 Running local listener smoke test: {args.command} {input_text}")
    result = cli_handler.handle_cli_command(
        input_text,
        response_url=args.target,
        user_id=args.user,
        mode=mode,
    )

    if not result.get("success"):
        print(f"❌ Failed to start listener flow: {result.get('error', 'unknown error')}")
        return 1

    session_id = result.get("session_id")
    if not session_id:
        print("❌ Listener flow returned without a session id.")
        return 1

    print(f"🧪 Session started: {session_id}")
    started_at = time.time()
    last_status = None
    last_snapshot = None

    while True:
        session = SESSIONS.get(session_id)
        if not session:
            print("ℹ️ Session no longer present in manager state; assuming it closed.")
            break

        status = session.get("status")
        snapshot = TerminalSessionManager.snapshot(session_id)
        if status != last_status:
            print(f"[status] {status}")
            last_status = status
        if snapshot and snapshot != last_snapshot:
            print("[snapshot]")
            print(snapshot)
            last_snapshot = snapshot

        if not session.get("active"):
            print("✅ Session marked inactive; smoke run complete.")
            break

        if time.time() - started_at > max(30, args.timeout):
            print(f"⏰ Timeout after {args.timeout}s; stopping session {session_id}.")
            TerminalSessionManager.close_session(session_id)
            return 2

        time.sleep(max(1, args.poll))

    session = SESSIONS.get(session_id, {})
    log_path = session.get("log_path")
    state_path = session.get("state_path")
    if log_path:
        print(f"📝 Session log: {log_path}")
    if state_path:
        print(f"🧾 Session state: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
