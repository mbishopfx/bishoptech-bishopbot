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
                db_path = Path(tmpdir) / "agent-context" / "memory.sqlite"

                self.assertTrue(vibes.exists())
                self.assertTrue(db_path.exists())

                conn = sqlite3.connect(db_path)
                try:
                    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertIn("resources", tables)
                    self.assertIn("sessions", tables)
                    self.assertIn("notes", tables)
                finally:
                    conn.close()

    def test_build_prompt_context_mentions_key_external_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"PROJECT_ROOT_DIR": tmpdir}, clear=False):
                context = agent_context_service.build_prompt_context()
                self.assertIn("Persistent operator context", context)
                self.assertIn("/Users/matthewbishop/.hermes", context)
                self.assertIn("/Users/matthewbishop/.openclaw", context)
                self.assertIn("agent-context/memory.sqlite", context)


if __name__ == "__main__":
    unittest.main()
