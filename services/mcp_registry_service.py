from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CONFIG


TABLE_ROW_RE = re.compile(r"^\|\s*\[(?P<name>.+?)\]\((?P<url>https?://[^)]+)\)\s*\|\s*(?P<description>.+?)\s*\|\s*$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_root() -> Path:
    return Path(CONFIG.get("PROJECT_ROOT_DIR") or ".").expanduser().resolve()


def catalog_repo_path() -> Path:
    configured = str(CONFIG.get("BISHOP_MCP_CATALOG_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "BishopTech.dev" / "bishoptech-api-mcps").resolve()


def registry_path() -> Path:
    configured = str(CONFIG.get("BISHOP_MCP_REGISTRY_PATH") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = _project_root() / path
        return path.resolve()
    return (_project_root() / "config" / "mcp_registry.json").resolve()


def catalog_snapshot_path() -> Path:
    return (_project_root() / "agent-context" / "mcp_catalog_snapshot.json").resolve()


def gemini_settings_path() -> Path:
    return (_project_root() / ".gemini" / "settings.json").resolve()


def project_gemini_md_path() -> Path:
    return (_project_root() / "GEMINI.md").resolve()


def _default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "catalog": {
            "source_dir": "${BISHOP_MCP_CATALOG_DIR}",
            "notes": "The live synced catalog is written to agent-context/mcp_catalog_snapshot.json.",
        },
        "notes": [
            "This file is BISHOP's curated MCP registry.",
            "Keep placeholders here until you are ready to enable a real MCP server connection.",
            "Only entries with enabled=true and a real command/url are written into .gemini/settings.json.",
        ],
        "servers": [
            {
                "key": "github",
                "label": "GitHub MCP",
                "enabled": False,
                "category": "development",
                "source_url": "https://apify.com/nexgendata/github-mcp-server?fpr=p2hrc6",
                "required_env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}",
                    },
                },
                "notes": "Recommended for repo search, PR workflows, and code intelligence.",
            },
            {
                "key": "web_search",
                "label": "Web Search MCP",
                "enabled": False,
                "category": "research",
                "source_url": "https://apify.com/abotapi/ai-search-mcp-server?fpr=p2hrc6",
                "required_env": [],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {},
                },
                "notes": "Useful for live search and citation-aware browsing from Gemini sessions.",
            },
            {
                "key": "google_maps",
                "label": "Google Maps MCP",
                "enabled": False,
                "category": "local-intelligence",
                "source_url": "https://apify.com/nexgendata/google-maps-mcp-server?fpr=p2hrc6",
                "required_env": [],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {},
                },
                "notes": "Strong fit for local lead generation and business validation workflows.",
            },
            {
                "key": "seo_intelligence",
                "label": "SEO Intelligence MCP",
                "enabled": False,
                "category": "marketing",
                "source_url": "https://apify.com/alizarin_refrigerator-owner/seo-intelligence-mcp-server?fpr=p2hrc6",
                "required_env": [],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {},
                },
                "notes": "Good fit for SEO, site audits, and local search intelligence.",
            },
            {
                "key": "airtable",
                "label": "Airtable MCP",
                "enabled": False,
                "category": "operations",
                "source_url": "https://apify.com/minute_contest/airtable-mcp-server?fpr=p2hrc6",
                "required_env": ["AIRTABLE_API_KEY"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "AIRTABLE_API_KEY": "${AIRTABLE_API_KEY}",
                    },
                },
                "notes": "Use when a project depends on Airtable-backed workflows or ops state.",
            },
            {
                "key": "asana",
                "label": "Asana MCP",
                "enabled": False,
                "category": "operations",
                "source_url": "https://apify.com/scraper_guru/asana-mcp-server?fpr=p2hrc6",
                "required_env": ["ASANA_ACCESS_TOKEN"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "ASANA_ACCESS_TOKEN": "${ASANA_ACCESS_TOKEN}",
                    },
                },
                "notes": "Good for PM workflows and task state inspection.",
            },
            {
                "key": "clickup",
                "label": "ClickUp MCP",
                "enabled": False,
                "category": "operations",
                "source_url": "https://apify.com/minute_contest/clickup-mcp-server?fpr=p2hrc6",
                "required_env": ["CLICKUP_API_TOKEN"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "CLICKUP_API_TOKEN": "${CLICKUP_API_TOKEN}",
                    },
                },
                "notes": "Use for task orchestration, sprint boards, and project execution visibility.",
            },
            {
                "key": "confluence",
                "label": "Confluence MCP",
                "enabled": False,
                "category": "knowledge",
                "source_url": "https://apify.com/scraper_guru/confluence-mcp-server?fpr=p2hrc6",
                "required_env": ["CONFLUENCE_API_TOKEN"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "CONFLUENCE_API_TOKEN": "${CONFLUENCE_API_TOKEN}",
                    },
                },
                "notes": "Useful when project context and SOPs live in Confluence.",
            },
            {
                "key": "trello",
                "label": "Trello MCP",
                "enabled": False,
                "category": "operations",
                "source_url": "https://apify.com/scraper_guru/trello-mcp-server?fpr=p2hrc6",
                "required_env": ["TRELLO_API_KEY", "TRELLO_TOKEN"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "TRELLO_API_KEY": "${TRELLO_API_KEY}",
                        "TRELLO_TOKEN": "${TRELLO_TOKEN}",
                    },
                },
                "notes": "Useful for board state, task movement, and project command flows.",
            },
            {
                "key": "wordpress",
                "label": "WordPress MCP",
                "enabled": False,
                "category": "content",
                "source_url": "https://apify.com/extremescrapes/wordpress-mcp-server?fpr=p2hrc6",
                "required_env": ["WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "WORDPRESS_BASE_URL": "${WORDPRESS_BASE_URL}",
                        "WORDPRESS_USERNAME": "${WORDPRESS_USERNAME}",
                        "WORDPRESS_APP_PASSWORD": "${WORDPRESS_APP_PASSWORD}",
                    },
                },
                "notes": "Strong fit for CMS publishing and content operations.",
            },
            {
                "key": "webflow",
                "label": "Webflow MCP",
                "enabled": False,
                "category": "content",
                "source_url": "https://apify.com/minute_contest/webflow-mcp-server?fpr=p2hrc6",
                "required_env": ["WEBFLOW_API_TOKEN"],
                "connection": {
                    "transport": "stdio",
                    "command": "",
                    "args": [],
                    "env": {
                        "WEBFLOW_API_TOKEN": "${WEBFLOW_API_TOKEN}",
                    },
                },
                "notes": "Useful for site content, CMS collections, and page operations.",
            },
        ],
    }


def ensure_registry_files() -> None:
    registry = registry_path()
    registry.parent.mkdir(parents=True, exist_ok=True)
    if not registry.exists():
        registry.write_text(json.dumps(_default_registry(), indent=2) + "\n", encoding="utf-8")
    gemini_settings = gemini_settings_path()
    gemini_settings.parent.mkdir(parents=True, exist_ok=True)
    if not gemini_settings.exists():
        gemini_settings.write_text(
            json.dumps({"security": {"disableYoloMode": False}, "mcpServers": {}}, indent=2) + "\n",
            encoding="utf-8",
        )
    snapshot_path = catalog_snapshot_path()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    if not snapshot_path.exists():
        snapshot = _build_catalog_snapshot()
        snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


def load_registry() -> dict[str, Any]:
    ensure_registry_files()
    return json.loads(registry_path().read_text(encoding="utf-8"))


def save_registry(payload: dict[str, Any]) -> None:
    registry = registry_path()
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _parse_mcp_rows(readme_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not readme_path.exists():
        return rows
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        match = TABLE_ROW_RE.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "name": match.group("name").strip(),
                "url": match.group("url").strip(),
                "description": match.group("description").strip(),
            }
        )
    return rows


def _build_catalog_snapshot() -> dict[str, Any]:
    snapshot = {
        "source_dir": str(catalog_repo_path()),
        "synced_at": _utc_now(),
        "available": False,
        "mcp_servers": [],
    }

    mcp_readme = catalog_repo_path() / "mcp-servers-apis" / "README.md"
    if mcp_readme.exists():
        rows = _parse_mcp_rows(mcp_readme)
        snapshot["available"] = True
        snapshot["mcp_servers"] = rows
        snapshot["mcp_count"] = len(rows)
    else:
        snapshot["mcp_count"] = 0
    return snapshot


def sync_catalog_snapshot() -> dict[str, Any]:
    ensure_registry_files()
    snapshot = _build_catalog_snapshot()
    path = catalog_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


def load_catalog_snapshot() -> dict[str, Any]:
    ensure_registry_files()
    path = catalog_snapshot_path()
    if not path.exists():
        return sync_catalog_snapshot()
    return json.loads(path.read_text(encoding="utf-8"))


def search_catalog(query: str, limit: int = 10) -> list[dict[str, str]]:
    normalized = (query or "").strip().lower()
    if not normalized:
        return []
    snapshot = load_catalog_snapshot()
    rows = snapshot.get("mcp_servers") or []
    ranked = []
    for row in rows:
        haystack = " ".join([row.get("name", ""), row.get("description", ""), row.get("url", "")]).lower()
        if normalized in haystack:
            score = 0
            if normalized in row.get("name", "").lower():
                score += 2
            if normalized in row.get("description", "").lower():
                score += 1
            ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    return [row for _, row in ranked[:limit]]


def _server_connection_payload(server: dict[str, Any]) -> dict[str, Any] | None:
    connection = dict(server.get("connection") or {})
    transport = str(connection.get("transport") or "stdio").strip().lower()
    if transport == "stdio":
        command = str(connection.get("command") or "").strip()
        args = connection.get("args") or []
        if not command:
            return None
        payload: dict[str, Any] = {"command": command}
        if args:
            payload["args"] = args
        env = connection.get("env") or {}
        if env:
            payload["env"] = env
        return payload
    if transport in {"http", "streamable-http"}:
        url = str(connection.get("url") or "").strip()
        if not url:
            return None
        payload = {"url": url}
        headers = connection.get("headers") or {}
        if headers:
            payload["headers"] = headers
        return payload
    return None


def enabled_servers() -> list[dict[str, Any]]:
    registry = load_registry()
    servers = registry.get("servers") or []
    active = []
    for server in servers:
        if not server.get("enabled"):
            continue
        payload = _server_connection_payload(server)
        if payload is None:
            continue
        active.append({"key": server["key"], "payload": payload, "label": server.get("label", server["key"])})
    return active


def generate_gemini_settings() -> dict[str, Any]:
    ensure_registry_files()
    current: dict[str, Any] = {}
    settings_path = gemini_settings_path()
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            current = {}

    current.setdefault("security", {"disableYoloMode": False})
    current["mcpServers"] = {item["key"]: item["payload"] for item in enabled_servers()}
    settings_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


def registry_summary() -> dict[str, Any]:
    registry = load_registry()
    snapshot = load_catalog_snapshot()
    servers = registry.get("servers") or []
    enabled = enabled_servers()
    placeholders = sum(1 for server in servers if not _server_connection_payload(server))
    return {
        "catalog_source_dir": str(catalog_repo_path()),
        "catalog_available": snapshot.get("available", False),
        "catalog_mcp_count": int(snapshot.get("mcp_count", 0) or 0),
        "registry_path": str(registry_path()),
        "catalog_snapshot_path": str(catalog_snapshot_path()),
        "gemini_settings_path": str(gemini_settings_path()),
        "project_gemini_md_path": str(project_gemini_md_path()),
        "registry_server_count": len(servers),
        "enabled_server_count": len(enabled),
        "placeholder_server_count": placeholders,
        "enabled_server_keys": [item["key"] for item in enabled],
    }
