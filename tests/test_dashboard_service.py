import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from config import CONFIG
from services import agent_context_service, dashboard_service


class DashboardServiceTests(unittest.TestCase):
    def test_tail_file_text_returns_last_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "session.log"
            path.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")

            tail = dashboard_service._tail_file_text(path, max_lines=2, max_chars=100)

        self.assertEqual(tail, "line4\nline5")

    def test_enqueue_dashboard_command_uses_worker_queue(self):
        queue = MagicMock()
        queue.name = "bishopbot_tasks"
        queue.enqueue.return_value.id = "job-123"

        with patch("services.dashboard_service._redis_queue", return_value=queue):
            payload = dashboard_service.enqueue_dashboard_command("/cli", "inspect the worker", "runtime:codex --full-auto")

        self.assertEqual(payload["job_id"], "job-123")
        queue.enqueue.assert_called_once_with(
            "local_worker.process_task",
            command="/cli",
            input_text="runtime:codex --full-auto inspect the worker",
            response_url="console:dashboard",
            user_id="dashboard",
        )

    @patch("services.dashboard_service.cli_handler.handle_cli_command")
    def test_run_glass_command_calls_cli_handler_directly(self, mock_handle_cli_command):
        mock_handle_cli_command.return_value = {
            "success": True,
            "output": "Session `sess-1234` started (runtime=gemini, mode=default).",
            "session_id": "sess-1234",
            "log_id": "log-1234",
        }

        payload = dashboard_service.run_glass_command("/cli", "inspect the worker")

        mock_handle_cli_command.assert_called_once_with(
            "inspect the worker",
            response_url="console:glass",
            user_id="glass",
            mode="gemini",
        )
        self.assertEqual(payload["command"], "/cli")
        self.assertEqual(payload["session_id"], "sess-1234")
        self.assertEqual(payload["output"], "Session `sess-1234` started (runtime=gemini, mode=default).")

    def test_enqueue_session_input_rejects_inactive_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            with patch.dict(
                CONFIG,
                {
                    "PROJECT_ROOT_DIR": tmpdir,
                    "SESSION_STATE_DIR": str(state_dir),
                },
                clear=False,
            ):
                agent_context_service.record_session_start(
                    "sess-complete",
                    runtime="gemini",
                    launch_mode="yolo",
                    user_id="U123",
                    response_target="console:dashboard",
                    original_request="do the thing",
                    refined_request="do the thing",
                    plan_text="1. do the thing",
                )
                agent_context_service.update_session_status("sess-complete", status="completed", final_summary="done")
                state_dir.mkdir(parents=True, exist_ok=True)
                (state_dir / "sess-complete.state").write_text("status=completed\n", encoding="utf-8")

                with patch("services.dashboard_service._redis_queue", return_value=MagicMock()):
                    with self.assertRaisesRegex(ValueError, "not active"):
                        dashboard_service.enqueue_session_input("sess-complete", "one more thing")

    def test_enqueue_session_input_rejects_argv_sessions(self):
        queue = MagicMock()
        queue.enqueue.return_value.id = "job-argv"

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            with patch.dict(
                CONFIG,
                {
                    "PROJECT_ROOT_DIR": tmpdir,
                    "SESSION_STATE_DIR": str(state_dir),
                },
                clear=False,
            ):
                agent_context_service.record_session_start(
                    "sess-argv",
                    runtime="codex",
                    launch_mode="full-auto",
                    user_id="U123",
                    response_target="console:dashboard",
                    original_request="inspect logs",
                    refined_request="inspect logs",
                    plan_text="1. inspect logs",
                )
                state_dir.mkdir(parents=True, exist_ok=True)
                (state_dir / "sess-argv.state").write_text("status=waiting_for_input\nprompt_transport=argv\n", encoding="utf-8")

                with patch("services.dashboard_service._redis_queue", return_value=queue):
                    with self.assertRaisesRegex(ValueError, "not active"):
                        dashboard_service.enqueue_session_input("sess-argv", "continue")

    def test_enqueue_session_input_accepts_running_session(self):
        queue = MagicMock()
        queue.enqueue.return_value.id = "job-456"

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            with patch.dict(
                CONFIG,
                {
                    "PROJECT_ROOT_DIR": tmpdir,
                    "SESSION_STATE_DIR": str(state_dir),
                },
                clear=False,
            ):
                agent_context_service.record_session_start(
                    "sess-live",
                    runtime="gemini",
                    launch_mode="yolo",
                    user_id="U123",
                    response_target="console:dashboard",
                    original_request="inspect logs",
                    refined_request="inspect logs",
                    plan_text="1. inspect logs",
                )
                state_dir.mkdir(parents=True, exist_ok=True)
                (state_dir / "sess-live.state").write_text("status=waiting_for_input\n", encoding="utf-8")

                with patch("services.dashboard_service._redis_queue", return_value=queue):
                    payload = dashboard_service.enqueue_session_input("sess-live", "continue with the next step")

        self.assertEqual(payload["job_id"], "job-456")
        queue.enqueue.assert_called_once_with(
            "local_worker.process_terminal_input",
            session_id="sess-live",
            input_text="continue with the next step",
            user_id="dashboard",
            response_url="console:dashboard",
            send_ack=False,
        )


if __name__ == "__main__":
    unittest.main()
