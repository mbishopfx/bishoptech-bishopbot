#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
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

from services import agent_context_service


def cmd_summary(_args):
    agent_context_service.ensure_context_assets()
    payload = {
        "vibes_path": str(agent_context_service.vibes_path()),
        "memory_db_path": str(agent_context_service.memory_db_path()),
        "memory_script_path": str(agent_context_service.memory_script_path()),
        "resources": agent_context_service.list_resources(),
        "recent_notes": agent_context_service.list_recent_notes(),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_resources(_args):
    agent_context_service.ensure_context_assets()
    for row in agent_context_service.list_resources():
        print(f"{row['category']}\t{row['key']}\t{row['path']}\t{row['description']}")
    return 0


def cmd_note(args):
    agent_context_service.add_note(
        args.title,
        args.content,
        kind=args.kind,
        session_id=args.session_id,
        pinned=args.pinned,
    )
    print("ok")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="BishopBot agent memory helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="Print context summary as JSON.")
    summary.set_defaults(func=cmd_summary)

    resources = subparsers.add_parser("resources", help="Print resource index.")
    resources.set_defaults(func=cmd_resources)

    note = subparsers.add_parser("note", help="Write a durable note.")
    note.add_argument("--title", required=True)
    note.add_argument("--content", required=True)
    note.add_argument("--kind", default="durable")
    note.add_argument("--session-id")
    note.add_argument("--pinned", action="store_true")
    note.set_defaults(func=cmd_note)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
