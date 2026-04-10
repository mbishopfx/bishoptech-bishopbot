import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from config import CONFIG
from services.shell_service import TerminalSnapshot, get_terminal_snapshot
from services.terminal_session_manager import TerminalSessionManager, SESSIONS
from services import session_output_service


class TerminalMonitoringTests(unittest.TestCase):
    def tearDown(self):
        SESSIONS.clear()

    def test_format_snapshot_output_strips_ansi_and_tails(self):
        output = "line1\n\x1b[31merror\x1b[0m line2\nline3\nline4"
        formatted = TerminalSessionManager._format_snapshot_output(output, tail_lines=2)
        self.assertEqual(formatted, "line3\nline4")

    def test_sanitize_snapshot_output_preserves_full_marker_buffer(self):
        output = "line1\n\x1b[31mTASK 2 COMPLETE\x1b[0m\nSESSION COMPLETE shipped it\n__BISHOPBOT_RUNTIME_EXIT__:codex:0\n"
        sanitized = TerminalSessionManager._sanitize_snapshot_output(output)
        self.assertIn("TASK 2 COMPLETE", sanitized)
        self.assertIn("SESSION COMPLETE shipped it", sanitized)
        self.assertIn("__BISHOPBOT_RUNTIME_EXIT__:codex:0", sanitized)

    def test_best_runtime_parse_output_prefers_durable_capture_when_terminal_tail_misses_markers(self):
        snapshot_output = "Codex footer noise only"
        capture_output = "TASK 2 COMPLETE\nSESSION COMPLETE shipped it\n__BISHOPBOT_RUNTIME_EXIT__:codex:0"
        selected = TerminalSessionManager._best_runtime_parse_output(snapshot_output, capture_output)
        self.assertEqual(selected, capture_output)

    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_uses_full_snapshot_for_completion_not_tail_only(self, mock_snapshot, mock_send_status):
        session_id = "sess1234"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir}, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "https://example.com/slack",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "running",
                    "needs_input": False,
                    "completed_at": None,
                    "runtime": "codex",
                    "runtime_label": "Codex",
                    "launch_mode": "full-auto",
                    "launch_mode_label": "Full Auto",
                    "launch_command": "codex exec --full-auto",
                    "prompt_transport": "argv",
                    "boot_delay_seconds": 0,
                    "runtime_metadata": {"controls": {"supports_interactive_controls": False}},
                    "terminal_exists": True,
                    "terminal_busy": False,
                    "completed_task_count": 0,
                    "final_summary": None,
                    "tasks": ["one", "two"],
                    "agent_mode": "codex",
                    "current_task_index": 0,
                    "plan_text": "1. one\n2. two",
                }
                from services import session_log_service, session_state_service
                SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])
                SESSIONS[session_id]["state_path"] = session_state_service.initialize_session_state(session_id, runtime="codex", launch_mode="full-auto")
                SESSIONS[session_id]["output_path"] = session_output_service.initialize_session_output(session_id)
                mock_snapshot.return_value = TerminalSnapshot(
                    window_id="123",
                    exists=True,
                    busy=False,
                    contents="line1\nTASK 2 COMPLETE\nSESSION COMPLETE shipped it\n__BISHOPBOT_RUNTIME_EXIT__:codex:0\nfooter1\nfooter2",
                )

                with patch.object(TerminalSessionManager, "_tail_lines_for_target", return_value=2):
                    TerminalSessionManager._poll_loop(session_id)

                session = SESSIONS[session_id]
                self.assertEqual(session["status"], "completed")
                self.assertEqual(session["completed_task_count"], 2)
                self.assertEqual(session["final_summary"], "shipped it")
                self.assertFalse(session["active"])
                self.assertTrue(mock_send_status.called)

    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_appends_snapshot_and_completion_to_runtime_log(self, mock_snapshot, mock_send_status):
        session_id = "sesslog1"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir}, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "https://example.com/slack",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "running",
                    "needs_input": False,
                    "completed_at": None,
                    "runtime": "codex",
                    "runtime_label": "Codex",
                    "launch_mode": "full-auto",
                    "launch_mode_label": "Full Auto",
                    "launch_command": "codex exec --full-auto",
                    "prompt_transport": "argv",
                    "boot_delay_seconds": 0,
                    "runtime_metadata": {"controls": {"supports_interactive_controls": False}},
                    "terminal_exists": True,
                    "terminal_busy": False,
                    "completed_task_count": 0,
                    "final_summary": None,
                    "tasks": ["one", "two"],
                    "agent_mode": "codex",
                    "current_task_index": 0,
                    "plan_text": "1. one\n2. two",
                }
                from services import session_log_service, session_state_service
                SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])
                SESSIONS[session_id]["state_path"] = session_state_service.initialize_session_state(session_id, runtime="codex", launch_mode="full-auto")
                SESSIONS[session_id]["output_path"] = session_output_service.initialize_session_output(session_id)

                mock_snapshot.return_value = TerminalSnapshot(
                    window_id="123",
                    exists=True,
                    busy=False,
                    contents="line1\nTASK 2 COMPLETE\nSESSION COMPLETE shipped it\n__BISHOPBOT_RUNTIME_EXIT__:codex:0\nfooter1\nfooter2",
                )

                with patch.object(TerminalSessionManager, "_tail_lines_for_target", return_value=2):
                    TerminalSessionManager._poll_loop(session_id)

                with open(SESSIONS[session_id]["log_path"], "r", encoding="utf-8") as handle:
                    logged = handle.read()
                self.assertIn("Terminal snapshot", logged)
                self.assertIn("Completed", logged)
                self.assertIn("SESSION COMPLETE shipped it", logged)

    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_recovers_clean_exit_from_runtime_state_when_terminal_closes(self, mock_snapshot, mock_send_status):
        session_id = "sessside"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir, "SESSION_STATE_DIR": tmpdir}, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "https://example.com/slack",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "running",
                    "needs_input": False,
                    "completed_at": None,
                    "runtime": "codex",
                    "runtime_label": "Codex",
                    "launch_mode": "full-auto",
                    "launch_mode_label": "Full Auto",
                    "launch_command": "codex exec --full-auto",
                    "prompt_transport": "argv",
                    "boot_delay_seconds": 0,
                    "runtime_metadata": {"controls": {"supports_interactive_controls": False}},
                    "terminal_exists": True,
                    "terminal_busy": False,
                    "completed_task_count": 0,
                    "final_summary": None,
                    "tasks": ["one"],
                    "agent_mode": "codex",
                    "current_task_index": 0,
                    "plan_text": "1. one",
                }
                from services import session_log_service, session_state_service
                SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])
                SESSIONS[session_id]["state_path"] = session_state_service.initialize_session_state(session_id, runtime="codex", launch_mode="full-auto")
                SESSIONS[session_id]["output_path"] = session_output_service.initialize_session_output(session_id)
                with open(SESSIONS[session_id]["state_path"], "w", encoding="utf-8") as handle:
                    handle.write("status=exited\nexit_code=0\nruntime=codex\nlaunch_mode=full-auto\n")

                mock_snapshot.return_value = TerminalSnapshot(
                    window_id="123",
                    exists=False,
                    busy=False,
                    contents="",
                )

                TerminalSessionManager._poll_loop(session_id)

                session = SESSIONS[session_id]
                self.assertEqual(session["status"], "completed")
                self.assertFalse(session["active"])
                self.assertEqual(session.get("exit_code"), 0)
                self.assertTrue(mock_send_status.called)

    @patch("services.terminal_session_manager.threading.Thread")
    @patch("services.terminal_session_manager.shell_service.send_input_to_terminal")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.shell_service.start_terminal_session")
    def test_start_session_creates_runtime_log_file(self, mock_start_terminal, mock_sleep, mock_send_input, mock_thread):
        mock_start_terminal.return_value = "789"
        thread_instance = MagicMock()
        mock_thread.return_value = thread_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir, "SESSION_STATE_DIR": tmpdir}, clear=False):
                session_id = TerminalSessionManager.start_session(
                    user_id="U789",
                    response_url="https://example.com/slack",
                    initial_command="ship it",
                    plan_text="1. Ship it",
                    tasks=["ship it"],
                    agent_mode="codex",
                    launch_mode="full-auto",
                )

                self.assertIsNotNone(session_id)
                log_path = SESSIONS[session_id]["log_path"]
                self.assertTrue(os.path.exists(log_path))
                with open(log_path, "r", encoding="utf-8") as handle:
                    logged = handle.read()
                self.assertIn("# Session", logged)
                self.assertIn("Runtime: Codex", logged)
                self.assertIn("Launch command: `codex exec --full-auto`", logged)
                self.assertTrue(os.path.exists(SESSIONS[session_id]["state_path"]))
                self.assertTrue(os.path.exists(SESSIONS[session_id]["output_path"]))

    @patch("services.shell_service.subprocess.run")
    @patch("services.shell_service.sys.platform", "darwin")
    def test_get_terminal_snapshot_parses_exists_busy_and_multiline_contents(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="exists:true\nbusy:true\ncontents:first line\nsecond line\nthird line\n"
        )

        snapshot = get_terminal_snapshot("123")

        self.assertEqual(
            snapshot,
            TerminalSnapshot(window_id="123", exists=True, busy=True, contents="first line\nsecond line\nthird line"),
        )

    @patch("services.terminal_session_manager.threading.Thread")
    @patch("services.terminal_session_manager.shell_service.send_input_to_terminal")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.shell_service.start_terminal_session")
    def test_start_session_skips_boot_sleep_for_argv_launches(self, mock_start_terminal, mock_sleep, mock_send_input, mock_thread):
        mock_start_terminal.return_value = "123"
        thread_instance = MagicMock()
        mock_thread.return_value = thread_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir, "SESSION_STATE_DIR": tmpdir}, clear=False):
                session_id = TerminalSessionManager.start_session(
                    user_id="U123",
                    response_url="https://example.com/slack",
                    initial_command="ship it",
                    plan_text="",
                    tasks=["ship it"],
                    agent_mode="codex",
                    launch_mode="full-auto",
                )

        self.assertIsNotNone(session_id)
        mock_sleep.assert_not_called()
        mock_send_input.assert_not_called()
        thread_instance.start.assert_called_once()
        self.assertEqual(SESSIONS[session_id]["prompt_transport"], "argv")
        mock_start_terminal.assert_called_once()
        _, kwargs = mock_start_terminal.call_args
        self.assertEqual(kwargs["launch_mode"], "full-auto")
        self.assertEqual(SESSIONS[session_id]["launch_mode"], "full-auto")
        self.assertEqual(SESSIONS[session_id]["launch_command"], "codex exec --full-auto")

    @patch("services.terminal_session_manager.threading.Thread")
    @patch("services.terminal_session_manager.shell_service.send_input_to_terminal")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.shell_service.start_terminal_session")
    def test_start_session_defaults_codex_to_full_auto_and_gemini_to_yolo(self, mock_start_terminal, mock_sleep, mock_send_input, mock_thread):
        mock_start_terminal.return_value = "124"
        thread_instance = MagicMock()
        mock_thread.return_value = thread_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir, "SESSION_STATE_DIR": tmpdir}, clear=False):
                codex_session_id = TerminalSessionManager.start_session(
                    user_id="U124",
                    response_url="https://example.com/slack",
                    initial_command="ship it",
                    plan_text="",
                    tasks=["ship it"],
                    agent_mode="codex",
                    launch_mode=None,
                )
                gemini_session_id = TerminalSessionManager.start_session(
                    user_id="U125",
                    response_url="https://example.com/slack",
                    initial_command="open the app",
                    plan_text="",
                    tasks=["open the app"],
                    agent_mode="gemini",
                    launch_mode=None,
                )

        self.assertEqual(SESSIONS[codex_session_id]["launch_mode"], "full-auto")
        self.assertEqual(SESSIONS[codex_session_id]["prompt_transport"], "argv")
        self.assertEqual(SESSIONS[codex_session_id]["launch_command"], "codex exec --full-auto")
        self.assertEqual(SESSIONS[gemini_session_id]["launch_mode"], "yolo")
        self.assertEqual(SESSIONS[gemini_session_id]["prompt_transport"], "stdin")
        self.assertEqual(SESSIONS[gemini_session_id]["launch_command"], "/opt/homebrew/bin/gemini --yolo")

    @patch("services.terminal_session_manager.threading.Thread")
    @patch("services.terminal_session_manager.shell_service.send_input_to_terminal")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.shell_service.start_terminal_session")
    def test_start_session_waits_and_injects_prompt_for_stdin_launches(self, mock_start_terminal, mock_sleep, mock_send_input, mock_thread):
        mock_start_terminal.return_value = "456"
        thread_instance = MagicMock()
        mock_thread.return_value = thread_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir, "SESSION_STATE_DIR": tmpdir}, clear=False):
                session_id = TerminalSessionManager.start_session(
                    user_id="U456",
                    response_url="https://example.com/slack",
                    initial_command="open the app",
                    plan_text="",
                    tasks=["open the app"],
                    agent_mode="gemini",
                    launch_mode="yolo",
                )

        self.assertIsNotNone(session_id)
        mock_sleep.assert_called_once()
        self.assertEqual(mock_send_input.call_count, 2)
        first_call = mock_send_input.call_args_list[0]
        second_call = mock_send_input.call_args_list[1]
        self.assertIn("gemini --yolo", first_call.kwargs.get("input_text", "") or first_call.args[0])
        self.assertEqual(first_call.kwargs.get("window_id", "456"), "456")
        self.assertEqual(second_call.args[0], "open the app")
        self.assertEqual(second_call.kwargs.get("window_id", "456"), "456")
        thread_instance.start.assert_called_once()
        self.assertEqual(SESSIONS[session_id]["prompt_transport"], "stdin")
        _, kwargs = mock_start_terminal.call_args
        self.assertEqual(kwargs["startup_command"], "cd /Users/matthewbishop/BishopBot")
        self.assertIsNone(kwargs["initial_prompt"])
        self.assertIsNone(kwargs["state_file"])
        self.assertIsNone(kwargs["output_file"])

    def test_runtime_state_heartbeat_freshness_helper(self):
        fresh = {"heartbeat_at": "2099-01-01T00:00:00Z"}
        stale = {"heartbeat_at": "2000-01-01T00:00:00Z"}

        with patch.dict(CONFIG, {"TERMINAL_STATE_HEARTBEAT_STALE_SECONDS": "15"}, clear=False):
            self.assertTrue(TerminalSessionManager._runtime_state_heartbeat_is_fresh(fresh))
            self.assertFalse(TerminalSessionManager._runtime_state_heartbeat_is_fresh(stale))
            self.assertFalse(TerminalSessionManager._runtime_state_heartbeat_is_fresh({}))

    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_waits_through_terminal_close_grace_before_marking_lost(self, mock_snapshot, mock_send_status, mock_sleep):
        session_id = "sessgrace"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {
                "SESSION_LOG_DIR": tmpdir,
                "SESSION_STATE_DIR": tmpdir,
                "TERMINAL_CLOSE_RECOVERY_GRACE_SECONDS": "20",
            }, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "https://example.com/slack",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "running",
                    "needs_input": False,
                    "completed_at": None,
                    "runtime": "codex",
                    "runtime_label": "Codex",
                    "launch_mode": "full-auto",
                    "launch_mode_label": "Full Auto",
                    "launch_command": "codex exec --full-auto",
                    "prompt_transport": "argv",
                    "boot_delay_seconds": 0,
                    "runtime_metadata": {"controls": {"supports_interactive_controls": False}},
                    "terminal_exists": True,
                    "terminal_busy": False,
                    "completed_task_count": 0,
                    "final_summary": None,
                    "tasks": ["one"],
                    "agent_mode": "codex",
                    "current_task_index": 0,
                    "plan_text": "1. one",
                }
                from services import session_log_service, session_state_service
                SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])
                SESSIONS[session_id]["state_path"] = session_state_service.initialize_session_state(session_id, runtime="codex", launch_mode="full-auto")
                SESSIONS[session_id]["output_path"] = session_output_service.initialize_session_output(session_id)

                mock_snapshot.side_effect = [
                    TerminalSnapshot(window_id="123", exists=False, busy=False, contents=""),
                    TerminalSnapshot(window_id="123", exists=False, busy=False, contents=""),
                ]

                with patch("services.terminal_session_manager.time.time", side_effect=[100.0, 100.0, 100.0, 100.0, 126.0, 126.0]):
                    TerminalSessionManager._poll_loop(session_id)

                session = SESSIONS[session_id]
                self.assertEqual(session["status"], "closed")
                self.assertFalse(session["active"])
                self.assertEqual(mock_send_status.call_count, 2)
                first_body = mock_send_status.call_args_list[0].args[1]
                second_body = mock_send_status.call_args_list[1].args[1]
                self.assertIn("waiting for runtime-state reconciliation", first_body)
                self.assertIn("Recovery grace elapsed: 20s", second_body)
                mock_sleep.assert_any_call(5)

    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_keeps_session_alive_when_runtime_heartbeat_is_fresh(self, mock_snapshot, mock_send_status, mock_sleep):
        session_id = "sessbeat"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {
                "SESSION_LOG_DIR": tmpdir,
                "SESSION_STATE_DIR": tmpdir,
                "TERMINAL_CLOSE_RECOVERY_GRACE_SECONDS": "0",
                "TERMINAL_STATE_HEARTBEAT_STALE_SECONDS": "15",
            }, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "https://example.com/slack",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "running",
                    "needs_input": False,
                    "completed_at": None,
                    "runtime": "codex",
                    "runtime_label": "Codex",
                    "launch_mode": "full-auto",
                    "launch_mode_label": "Full Auto",
                    "launch_command": "codex exec --full-auto",
                    "prompt_transport": "argv",
                    "boot_delay_seconds": 0,
                    "runtime_metadata": {"controls": {"supports_interactive_controls": False}},
                    "terminal_exists": True,
                    "terminal_busy": False,
                    "completed_task_count": 0,
                    "final_summary": None,
                    "tasks": ["one"],
                    "agent_mode": "codex",
                    "current_task_index": 0,
                    "plan_text": "1. one",
                }
                from services import session_log_service, session_state_service
                SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])
                SESSIONS[session_id]["state_path"] = session_state_service.initialize_session_state(session_id, runtime="codex", launch_mode="full-auto")
                SESSIONS[session_id]["output_path"] = session_output_service.initialize_session_output(session_id)

                mock_snapshot.side_effect = [
                    TerminalSnapshot(window_id="123", exists=False, busy=False, contents=""),
                    TerminalSnapshot(window_id="123", exists=False, busy=False, contents=""),
                ]

                def mutate_sleep(seconds):
                    if seconds == 5:
                        with open(SESSIONS[session_id]["state_path"], "w", encoding="utf-8") as handle:
                            handle.write("status=exited\nexit_code=0\nruntime=codex\nlaunch_mode=full-auto\n")

                mock_sleep.side_effect = mutate_sleep

                with open(SESSIONS[session_id]["state_path"], "w", encoding="utf-8") as handle:
                    handle.write("status=running\nheartbeat_at=2099-01-01T00:00:00Z\nruntime=codex\nlaunch_mode=full-auto\n")

                TerminalSessionManager._poll_loop(session_id)

                session = SESSIONS[session_id]
                self.assertEqual(session["status"], "completed")
                self.assertFalse(session["active"])
                self.assertEqual(mock_send_status.call_count, 2)
                first_body = mock_send_status.call_args_list[0].args[1]
                second_body = mock_send_status.call_args_list[1].args[1]
                self.assertIn("heartbeat still looks alive", first_body)
                self.assertIn("marked complete", second_body)
                mock_sleep.assert_any_call(5)

    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_can_complete_from_durable_output_capture_when_terminal_snapshot_is_empty(self, mock_snapshot, mock_send_status):
        session_id = "sesscapture"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir, "SESSION_STATE_DIR": tmpdir, "SESSION_OUTPUT_DIR": tmpdir}, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "https://example.com/slack",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "running",
                    "needs_input": False,
                    "completed_at": None,
                    "runtime": "codex",
                    "runtime_label": "Codex",
                    "launch_mode": "full-auto",
                    "launch_mode_label": "Full Auto",
                    "launch_command": "codex exec --full-auto",
                    "prompt_transport": "argv",
                    "boot_delay_seconds": 0,
                    "runtime_metadata": {"controls": {"supports_interactive_controls": False}},
                    "terminal_exists": True,
                    "terminal_busy": False,
                    "completed_task_count": 0,
                    "final_summary": None,
                    "tasks": ["one", "two"],
                    "agent_mode": "codex",
                    "current_task_index": 0,
                    "plan_text": "1. one\n2. two",
                }
                from services import session_log_service, session_state_service
                SESSIONS[session_id]["log_path"] = session_log_service.initialize_session_log(session_id, SESSIONS[session_id])
                SESSIONS[session_id]["state_path"] = session_state_service.initialize_session_state(session_id, runtime="codex", launch_mode="full-auto")
                SESSIONS[session_id]["output_path"] = session_output_service.initialize_session_output(session_id)
                with open(SESSIONS[session_id]["output_path"], "w", encoding="utf-8") as handle:
                    handle.write("TASK 2 COMPLETE\nSESSION COMPLETE shipped it\n__BISHOPBOT_RUNTIME_EXIT__:codex:0\n")

                mock_snapshot.return_value = TerminalSnapshot(
                    window_id="123",
                    exists=False,
                    busy=False,
                    contents="",
                )

                TerminalSessionManager._poll_loop(session_id)

                session = SESSIONS[session_id]
                self.assertEqual(session["status"], "completed")
                self.assertFalse(session["active"])
                self.assertEqual(session["completed_task_count"], 2)
                self.assertEqual(session["final_summary"], "shipped it")
                self.assertTrue(mock_send_status.called)


if __name__ == "__main__":
    unittest.main()
