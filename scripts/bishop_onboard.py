#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if VENV_PYTHON.exists():
    try:
        if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
            os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])
    except Exception:
        pass

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import dotenv_values


ENV_TEMPLATE_PATH = PROJECT_ROOT / ".env.example"
ENV_PATH = PROJECT_ROOT / ".env"
MANIFEST_PATH = PROJECT_ROOT / "manifest.json"


def detect_paths() -> dict[str, str]:
    home = Path.home()
    return {
        "PROJECT_ROOT_DIR": str(PROJECT_ROOT),
        "HERMES_HOME": str(home / ".hermes"),
        "OPENCLAW_HOME": str(home / ".openclaw"),
        "SHARED_SKILLS_DIR": str(home / ".agents" / "skills"),
        "GEMINI_SKILLS_DIR": str(home / ".gemini" / "skills"),
        "REDIS_URL": "redis://localhost:6379/0",
        "TASK_QUEUE_NAME": "bishopbot_tasks",
        "BISHOP_BRAND_NAME": "BISHOP",
        "BISHOP_DASHBOARD_PORT": "3113",
        "GEMINI_CLI_ARGS": "--yolo",
        "GEMINI_CLI_ARGS_YOLO": "--yolo",
        "CODEX_CLI_ARGS": "exec --full-auto",
        "CODEX_CLI_ARGS_FULL_AUTO": "exec --full-auto",
        "CODEX_CLI_ARGS_YOLO": "--yolo",
        "GEMINI_PROMPT_TRANSPORT": "stdin",
        "CODEX_PROMPT_TRANSPORT": "argv",
        "GEMINI_BOOT_DELAY_SECONDS": "10",
        "CODEX_BOOT_DELAY_SECONDS": "5",
    }


def load_template_lines() -> list[str]:
    return ENV_TEMPLATE_PATH.read_text(encoding="utf-8").splitlines()


def render_env() -> str:
    detected = detect_paths()
    rendered: list[str] = []
    for line in load_template_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            rendered.append(line)
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        replacement = detected.get(key, value)
        rendered.append(f"{key}={replacement}")
    return "\n".join(rendered) + "\n"


def read_env_values() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    return {k: v for k, v in dotenv_values(ENV_PATH).items() if v is not None}


def write_env(force: bool = False) -> int:
    if ENV_PATH.exists() and not force:
        print(f"{ENV_PATH} already exists. Re-run with --force to overwrite.")
        return 1
    ENV_PATH.write_text(render_env(), encoding="utf-8")
    print(f"Wrote {ENV_PATH}")
    return 0


def _status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def doctor() -> int:
    env_values = read_env_values()
    detected = detect_paths()
    rows = [
        ("project_root", True, str(PROJECT_ROOT)),
        (".env", ENV_PATH.exists(), str(ENV_PATH)),
        ("manifest.json", MANIFEST_PATH.exists(), str(MANIFEST_PATH)),
        ("python_venv", VENV_PYTHON.exists(), str(VENV_PYTHON)),
        ("gemini_cli", shutil.which("gemini") is not None, shutil.which("gemini") or "not found"),
        ("codex_cli", shutil.which("codex") is not None, shutil.which("codex") or "not found"),
        ("redis_server", shutil.which("redis-server") is not None, shutil.which("redis-server") or "not found"),
    ]

    for key in ("HERMES_HOME", "OPENCLAW_HOME", "SHARED_SKILLS_DIR", "GEMINI_SKILLS_DIR"):
        resolved = Path(env_values.get(key) or detected[key]).expanduser()
        rows.append((key.lower(), resolved.exists(), str(resolved)))

    required_env = ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_SIGNING_SECRET")
    for key in required_env:
        rows.append((key.lower(), bool(env_values.get(key)), "set" if env_values.get(key) else "unset"))

    print("BISHOP onboarding doctor\n")
    for label, ok, detail in rows:
        print(f"[{_status(ok):7}] {label:22} {detail}")

    print("\nRecommended next steps:")
    if not ENV_PATH.exists():
        print(f"- Run `{__file__} init-env`")
    if not env_values.get("SLACK_BOT_TOKEN"):
        print("- Fill Slack tokens in .env")
    print(f"- Import or update Slack manifest from {MANIFEST_PATH}")
    print("- Install dependencies: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements_local.txt`")
    print("- Start the full local stack with `./start.sh`")
    print("- Dashboard will be served at http://localhost:3113 unless BISHOP_DASHBOARD_PORT overrides it")

    critical_ok = all(ok for _, ok, _ in rows[:4])
    return 0 if critical_ok else 1


def print_paths() -> int:
    print(json.dumps(detect_paths(), indent=2))
    return 0


def print_next_steps() -> int:
    print(
        "\n".join(
            [
                "BISHOP quickstart:",
                "1. Clone the repo.",
                "2. Create a venv and install `requirements_local.txt`.",
                "3. Run `./scripts/bishop_onboard.py init-env`.",
                "4. Fill Slack tokens and any optional API keys in `.env`.",
                "5. Import `manifest.json` into your Slack app and reinstall it.",
                "6. Start the full local stack with `./start.sh`.",
                "7. Open the dashboard at http://localhost:3113.",
            ]
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BISHOP onboarding and environment checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_env = subparsers.add_parser("init-env", help="Write a starter .env file using detected local paths.")
    init_env.add_argument("--force", action="store_true", help="Overwrite an existing .env file.")
    init_env.set_defaults(func=lambda args: write_env(force=args.force))

    doctor_cmd = subparsers.add_parser("doctor", help="Run local environment checks.")
    doctor_cmd.set_defaults(func=lambda _args: doctor())

    paths_cmd = subparsers.add_parser("paths", help="Print detected default paths as JSON.")
    paths_cmd.set_defaults(func=lambda _args: print_paths())

    next_steps = subparsers.add_parser("next-steps", help="Print a concise install flow.")
    next_steps.set_defaults(func=lambda _args: print_next_steps())

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
