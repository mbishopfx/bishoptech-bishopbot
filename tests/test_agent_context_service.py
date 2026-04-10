import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import CONFIG
from services import agent_context_service


class AgentContextServiceTests(unittest.TestCase):
    def test_ensure_context_assets_creates_vibes_and_memory_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"PROJECT_ROOT_DIR": tmpdir}, clear=False):
                agent_context_service.ensure_context_assets()

                vibes = Path(tmpdir) / "agent-context" / "vibes.md"
                vibes_full = Path(tmpdir) / "agent-context" / "vibes-full.md"
                db_path = Path(tmpdir) / "agent-context" / "memory.sqlite"

                self.assertTrue(vibes.exists())
                self.assertTrue(vibes_full.exists())
                self.assertTrue(db_path.exists())

                conn = sqlite3.connect(db_path)
                try:
                    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertIn("resources", tables)
                    self.assertIn("sessions", tables)
                    self.assertIn("notes", tables)
                finally:
                    conn.close()

    def test_build_prompt_context_uses_vibes_full_and_handles_missing_openclaw_soul(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                CONFIG,
                {"PROJECT_ROOT_DIR": tmpdir, "OPENCLAW_HOME": str(Path(tmpdir) / ".openclaw-missing")},
                clear=False,
            ):
                context = agent_context_service.build_prompt_context()
                self.assertIn("Persistent operator context", context)
                self.assertIn("vibes-full.md", context)
                self.assertIn("agent-context/memory.sqlite", context)
                self.assertIn("OpenClaw soul reference: `null`", context)

    def test_build_prompt_context_points_to_openclaw_soul_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            openclaw_home = Path(tmpdir) / ".openclaw"
            soul_path = openclaw_home / "workspace" / "soul.md"
            soul_path.parent.mkdir(parents=True, exist_ok=True)
            soul_path.write_text("# tone", encoding="utf-8")

            with patch.dict(
                CONFIG,
                {"PROJECT_ROOT_DIR": tmpdir, "OPENCLAW_HOME": str(openclaw_home)},
                clear=False,
            ):
                context = agent_context_service.build_prompt_context()

            self.assertIn(str(soul_path), context)


if __name__ == "__main__":
    unittest.main()
