import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from config import CONFIG
from services.shell_service import TerminalSnapshot, get_terminal_snapshot
from services.terminal_session_manager import TerminalSessionManager, SESSIONS
from services import session_output_service, terminal_observer_service


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

    def test_terminal_observer_suggests_navigation_controls_for_menu_prompt(self):
        observation = terminal_observer_service.observe_terminal(
            session_status="waiting_for_input",
            output="Choose an option\n❯ Continue\n  Cancel",
            prompt_transport="stdin",
            terminal_busy=False,
            runtime_label="Gemini",
            launch_mode="yolo",
        )

        self.assertEqual(observation.state, "awaiting_input")
        self.assertIn("ENTER", observation.controls)
        self.assertIn("ARROW_UP", observation.controls)
        self.assertIn("ARROW_DOWN", observation.controls)
        self.assertIn("STATUS", observation.controls)

    @patch("services.terminal_session_manager.shell_service.send_input_to_terminal")
    @patch("services.terminal_session_manager.shell_service.send_control_to_terminal")
    def test_send_input_routes_special_controls_to_terminal_control_path(self, mock_send_control, mock_send_input):
        session_id = "sessctrl1"
        SESSIONS[session_id] = {
            "window_id": "123",
            "tty_path": "/dev/ttys123",
            "active": True,
            "runtime": "gemini",
        }
        mock_send_control.return_value = True

        ok = TerminalSessionManager.send_input(session_id, "ARROW_DOWN")

        self.assertTrue(ok)
        mock_send_control.assert_called_once_with("ARROW_DOWN", window_id="123", tty_path="/dev/ttys123")
        mock_send_input.assert_not_called()

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

    @patch("services.terminal_session_manager.agent_context_service.update_session_status")
    @patch("services.terminal_session_manager.TerminalSessionManager.send_status_to_slack")
    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    def test_poll_loop_persists_session_status_transitions(self, mock_snapshot, mock_send_status, mock_update_status):
        session_id = "sessctx1"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(CONFIG, {"SESSION_LOG_DIR": tmpdir}, clear=False):
                SESSIONS[session_id] = {
                    "window_id": "123",
                    "response_url": "slack:C123:1712345678.123456",
                    "user_id": "U123",
                    "last_output": "",
                    "last_raw_output": "",
                    "last_summary_output": "",
                    "active": True,
                    "start_time": time.time(),
                    "last_poll_time": time.time(),
                    "status": "booting",
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
                    contents="TASK 2 COMPLETE\nSESSION COMPLETE shipped it\n__BISHOPBOT_RUNTIME_EXIT__:codex:0\n",
                )

                with patch.object(TerminalSessionManager, "_tail_lines_for_target", return_value=2):
                    TerminalSessionManager._poll_loop(session_id)

                mock_update_status.assert_any_call(
                    session_id,
                    status="completed",
                    response_target="slack:C123:1712345678.123456",
                    final_summary="shipped it",
                )

    @patch("services.terminal_session_manager.session_link_service.set_slack_thread_session")
    @patch("services.terminal_session_manager.slack_service.send_target_message")
    def test_send_status_to_slack_creates_thread_root_for_slack_channel_targets(self, mock_send_target, mock_set_thread):
        session_id = "sessslk1"
        SESSIONS[session_id] = {
            "window_id": "123",
            "response_url": "slack:C123",
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
            "runtime": "gemini",
            "runtime_label": "Gemini",
            "launch_mode": "yolo",
            "launch_mode_label": "YOLO",
            "launch_command": "/opt/homebrew/bin/gemini --yolo",
            "prompt_transport": "stdin",
            "boot_delay_seconds": 10,
            "runtime_metadata": {"controls": {"supports_interactive_controls": True}},
            "terminal_exists": True,
            "terminal_busy": True,
            "completed_task_count": 0,
            "final_summary": None,
            "tasks": ["one"],
            "agent_mode": "gemini",
            "current_task_index": 0,
            "plan_text": "1. one",
        }
        mock_send_target.return_value = {"ok": True, "ts": "1712345678.123456"}

        TerminalSessionManager.send_status_to_slack(session_id, "runtime booted")

        self.assertEqual(SESSIONS[session_id]["response_url"], "slack:C123:1712345678.123456")
        mock_set_thread.assert_called_once_with("C123", "1712345678.123456", session_id)
        mock_send_target.assert_called_once()

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

    @patch("services.shell_service.subprocess.run")
    @patch("services.shell_service.sys.platform", "darwin")
    def test_start_terminal_session_does_not_activate_terminal_by_default(self, mock_run):
        from services import shell_service

        mock_run.return_value = MagicMock(stdout="123\n")

        with patch.dict(CONFIG, {"TERMINAL_ACTIVATE_ON_LAUNCH": "false"}, clear=False):
            window_id = shell_service.start_terminal_session(runtime="gemini", startup_command="echo hi")

        self.assertEqual(window_id, "123")
        script = mock_run.call_args.args[0][2]
        self.assertNotIn("activate", script)
        self.assertIn('set newTab to do script "echo hi"', script)

    @patch("services.shell_service.subprocess.run")
    @patch("services.shell_service.sys.platform", "darwin")
    def test_send_input_uses_background_do_script_by_default(self, mock_run):
        from services import shell_service

        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")

        with patch.dict(CONFIG, {"TERMINAL_ACTIVATE_ON_INPUT": "false"}, clear=False):
            ok = shell_service.send_input_to_terminal("hello world", window_id="123")

        self.assertTrue(ok)
        script = mock_run.call_args.args[0][2]
        self.assertIn('do script "hello world" in selected tab of window id 123', script)
        self.assertNotIn("System Events", script)
        self.assertNotIn("activate", script)

    @patch("services.shell_service.subprocess.run")
    @patch("services.shell_service.sys.platform", "darwin")
    def test_send_input_with_tty_uses_terminal_ui_keystrokes(self, mock_run):
        from services import shell_service

        mock_run.side_effect = [
            MagicMock(stdout="Code\n", returncode=0, stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        with patch.dict(CONFIG, {"TERMINAL_ACTIVATE_ON_INPUT": "false"}, clear=False):
            ok = shell_service.send_input_to_terminal("hello world", window_id="123", tty_path="/dev/ttys123", submit=True)

        self.assertTrue(ok)
        self.assertEqual(mock_run.call_args_list[1].args[0][0], "pbpaste")
        self.assertEqual(mock_run.call_args_list[2].args[0][0], "pbcopy")
        script = mock_run.call_args_list[3].args[0][2]
        self.assertIn('keystroke "v" using command down', script)
        self.assertIn("key code 36", script)
        self.assertIn('tell application "Code"', script)
        self.assertEqual(mock_run.call_args_list[4].args[0][0], "pbcopy")

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
    @patch("services.terminal_session_manager.shell_service.get_terminal_tty")
    @patch("services.terminal_session_manager.shell_service.send_input_to_terminal")
    @patch("services.terminal_session_manager.TerminalSessionManager._wait_for_runtime_ready", return_value=True)
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.shell_service.start_terminal_session")
    def test_start_session_waits_and_injects_prompt_for_stdin_launches(self, mock_start_terminal, mock_sleep, mock_wait_ready, mock_send_input, mock_get_tty, mock_thread):
        mock_start_terminal.return_value = "456"
        mock_get_tty.return_value = "/dev/ttys456"
        thread_instance = MagicMock()
        mock_thread.return_value = thread_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                CONFIG,
                {
                    "SESSION_LOG_DIR": tmpdir,
                    "SESSION_STATE_DIR": tmpdir,
                    "TERMINAL_PROMPT_ENTER_DELAY_SECONDS": "5",
                },
                clear=False,
            ):
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
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(mock_sleep.call_args_list[0].args[0], 2)
        self.assertEqual(mock_sleep.call_args_list[1].args[0], 5)
        self.assertEqual(mock_send_input.call_count, 3)
        mock_wait_ready.assert_called_once()
        self.assertEqual(mock_wait_ready.call_args.kwargs["window_id"], "456")
        first_call = mock_send_input.call_args_list[0]
        second_call = mock_send_input.call_args_list[1]
        third_call = mock_send_input.call_args_list[2]
        self.assertIn("gemini --yolo", first_call.kwargs.get("input_text", "") or first_call.args[0])
        self.assertEqual(first_call.kwargs.get("window_id", "456"), "456")
        self.assertEqual(second_call.args[0], "open the app")
        self.assertEqual(second_call.kwargs.get("window_id", "456"), "456")
        self.assertEqual(second_call.kwargs.get("tty_path"), "/dev/ttys456")
        self.assertFalse(second_call.kwargs.get("submit", True))
        self.assertEqual(third_call.args[0], "")
        self.assertEqual(third_call.kwargs.get("tty_path"), "/dev/ttys456")
        self.assertTrue(third_call.kwargs.get("submit", False))
        thread_instance.start.assert_called_once()
        self.assertEqual(SESSIONS[session_id]["prompt_transport"], "stdin")
        self.assertEqual(SESSIONS[session_id]["tty_path"], "/dev/ttys456")
        self.assertEqual(SESSIONS[session_id]["prompt_enter_delay_seconds"], 5)
        _, kwargs = mock_start_terminal.call_args
        self.assertEqual(kwargs["startup_command"], "cd /Users/matthewbishop/BishopBot")
        self.assertIsNone(kwargs["initial_prompt"])
        self.assertIsNone(kwargs["state_file"])
        self.assertIsNone(kwargs["output_file"])

    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.session_output_service.read_output_file")
    def test_wait_for_runtime_ready_requires_gemini_input_prompt(self, mock_read_output, mock_sleep, mock_snapshot):
        adapter = TerminalSessionManager
        runtime_adapter = __import__("services.runtime_adapters", fromlist=["get_runtime_adapter"]).get_runtime_adapter("gemini")
        mock_read_output.side_effect = [
            "",
            "[Gemini] starting in YOLO automation mode...\nGemini CLI v0.37.1\nSigned in with Google /auth\n",
            "Type your message or @path/to/file",
        ]
        mock_snapshot.return_value = MagicMock(contents="", exists=True, busy=True)

        ready = adapter._wait_for_runtime_ready(runtime_adapter, "/tmp/fake.log", launch_mode="yolo", window_id="123")

        self.assertTrue(ready)
        self.assertGreaterEqual(mock_read_output.call_count, 2)

    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.session_output_service.read_output_file")
    def test_wait_for_runtime_ready_blocks_on_gemini_auth_screen(self, mock_read_output, mock_sleep, mock_snapshot):
        adapter = TerminalSessionManager
        runtime_adapter = __import__("services.runtime_adapters", fromlist=["get_runtime_adapter"]).get_runtime_adapter("gemini")
        mock_read_output.return_value = ""
        mock_snapshot.side_effect = [
            MagicMock(contents="Gemini CLI v0.37.1\nWaiting for authentication...", exists=True, busy=True),
            MagicMock(contents="Type your message or @path/to/file", exists=True, busy=True),
        ]

        ready = adapter._wait_for_runtime_ready(runtime_adapter, "/tmp/fake.log", launch_mode="yolo", window_id="123")

        self.assertTrue(ready)

    @patch("services.terminal_session_manager.shell_service.get_terminal_snapshot")
    @patch("services.terminal_session_manager.time.sleep")
    @patch("services.terminal_session_manager.session_output_service.read_output_file")
    def test_wait_for_runtime_ready_uses_live_terminal_snapshot_when_log_lags(self, mock_read_output, mock_sleep, mock_snapshot):
        adapter = TerminalSessionManager
        runtime_adapter = __import__("services.runtime_adapters", fromlist=["get_runtime_adapter"]).get_runtime_adapter("gemini")
        mock_read_output.return_value = "[Gemini] starting in YOLO automation mode..."
        mock_snapshot.side_effect = [
            MagicMock(contents="", exists=True, busy=True),
            MagicMock(contents="Gemini CLI v0.37.1\nPlan: Google AI Ultra for Business\n", exists=True, busy=True),
            MagicMock(contents="Type your message or @path/to/file", exists=True, busy=True),
        ]

        ready = adapter._wait_for_runtime_ready(runtime_adapter, "/tmp/fake.log", launch_mode="yolo", window_id="123")

        self.assertTrue(ready)

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
