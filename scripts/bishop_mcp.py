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

from services import mcp_registry_service


def cmd_init(_args: argparse.Namespace) -> int:
    mcp_registry_service.ensure_registry_files()
    payload = mcp_registry_service.registry_summary()
    print(json.dumps(payload, indent=2))
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(mcp_registry_service.registry_summary(), indent=2))
    return 0


def cmd_sync_catalog(_args: argparse.Namespace) -> int:
    payload = mcp_registry_service.sync_catalog_snapshot()
    print(json.dumps(payload, indent=2))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    rows = mcp_registry_service.search_catalog(args.query, limit=args.limit)
    print(json.dumps(rows, indent=2))
    return 0


def cmd_build_gemini(_args: argparse.Namespace) -> int:
    payload = mcp_registry_service.generate_gemini_settings()
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BISHOP MCP catalog, registry, and Gemini settings helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init", help="Create the BISHOP MCP registry and initial Gemini settings scaffolding.")
    init_cmd.set_defaults(func=cmd_init)

    status_cmd = subparsers.add_parser("status", help="Print the current MCP catalog and registry summary.")
    status_cmd.set_defaults(func=cmd_status)

    sync_cmd = subparsers.add_parser("sync-catalog", help="Sync the external MCP catalog repo into the local snapshot.")
    sync_cmd.set_defaults(func=cmd_sync_catalog)

    search_cmd = subparsers.add_parser("search", help="Search the synced MCP catalog snapshot.")
    search_cmd.add_argument("query", help="Case-insensitive search term for name/description/url.")
    search_cmd.add_argument("--limit", type=int, default=10, help="Maximum number of matches to return.")
    search_cmd.set_defaults(func=cmd_search)

    build_cmd = subparsers.add_parser("build-gemini", help="Generate .gemini/settings.json from enabled registry entries.")
    build_cmd.set_defaults(func=cmd_build_gemini)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
