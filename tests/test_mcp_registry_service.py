import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import CONFIG
from services import mcp_registry_service


class MCPRegistryServiceTests(unittest.TestCase):
    def test_ensure_registry_files_creates_registry_and_gemini_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "project"
            catalog_root = Path(tmpdir) / "catalog"
            (catalog_root / "mcp-servers-apis").mkdir(parents=True, exist_ok=True)
            (catalog_root / "mcp-servers-apis" / "README.md").write_text(
                "| API Name | Description |\n"
                "|----------|-------------|\n"
                "| [GitHub MCP](https://example.com/github) | Repo tools |\n",
                encoding="utf-8",
            )

            with patch.dict(
                CONFIG,
                {
                    "PROJECT_ROOT_DIR": str(project_root),
                    "BISHOP_MCP_CATALOG_DIR": str(catalog_root),
                },
                clear=False,
            ):
                mcp_registry_service.ensure_registry_files()

                self.assertTrue((project_root / "config" / "mcp_registry.json").exists())
                self.assertTrue((project_root / ".gemini" / "settings.json").exists())
                self.assertTrue((project_root / "agent-context" / "mcp_catalog_snapshot.json").exists())

    def test_sync_catalog_snapshot_parses_mcp_markdown_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "project"
            catalog_root = Path(tmpdir) / "catalog"
            readme = catalog_root / "mcp-servers-apis" / "README.md"
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text(
                "| API Name | Description |\n"
                "|----------|-------------|\n"
                "| [GitHub MCP](https://example.com/github) | Repo tools |\n"
                "| [Brave Search MCP](https://example.com/brave) | Search tools |\n",
                encoding="utf-8",
            )

            with patch.dict(
                CONFIG,
                {
                    "PROJECT_ROOT_DIR": str(project_root),
                    "BISHOP_MCP_CATALOG_DIR": str(catalog_root),
                },
                clear=False,
            ):
                snapshot = mcp_registry_service.sync_catalog_snapshot()

            self.assertTrue(snapshot["available"])
            self.assertEqual(snapshot["mcp_count"], 2)
            self.assertEqual(snapshot["mcp_servers"][0]["name"], "GitHub MCP")
            self.assertEqual(snapshot["mcp_servers"][1]["url"], "https://example.com/brave")

    def test_generate_gemini_settings_writes_only_enabled_concrete_servers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "project"
            catalog_root = Path(tmpdir) / "catalog"
            (catalog_root / "mcp-servers-apis").mkdir(parents=True, exist_ok=True)
            (catalog_root / "mcp-servers-apis" / "README.md").write_text("", encoding="utf-8")

            with patch.dict(
                CONFIG,
                {
                    "PROJECT_ROOT_DIR": str(project_root),
                    "BISHOP_MCP_CATALOG_DIR": str(catalog_root),
                },
                clear=False,
            ):
                mcp_registry_service.ensure_registry_files()
                registry = mcp_registry_service.load_registry()
                registry["servers"].append(
                    {
                        "key": "test_server",
                        "label": "Test Server",
                        "enabled": True,
                        "connection": {
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "@test/mcp-server"],
                            "env": {"TEST_TOKEN": "${TEST_TOKEN}"},
                        },
                    }
                )
                mcp_registry_service.save_registry(registry)
                generated = mcp_registry_service.generate_gemini_settings()

                self.assertIn("mcpServers", generated)
                self.assertIn("test_server", generated["mcpServers"])
                self.assertEqual(generated["mcpServers"]["test_server"]["command"], "npx")
                self.assertNotIn("github", generated["mcpServers"])

                settings = json.loads((project_root / ".gemini" / "settings.json").read_text(encoding="utf-8"))
                self.assertIn("test_server", settings["mcpServers"])


if __name__ == "__main__":
    unittest.main()
