import unittest
from unittest.mock import patch

from config import CONFIG
from services.runtime_adapters import get_runtime_adapter, parse_runtime_invocation


class RuntimeAdapterTests(unittest.TestCase):
    def test_gemini_defaults_to_stdin_prompt_transport(self):
        adapter = get_runtime_adapter("gemini")
        with patch.dict(CONFIG, {"GEMINI_CLI_ARGS": "--yolo", "GEMINI_PROMPT_TRANSPORT": "stdin"}, clear=False):
            self.assertEqual(adapter.prompt_transport(), "stdin")
            command = adapter.launch_bootstrap_command("/tmp/project", initial_prompt="do work")
            self.assertIn("gemini --yolo", command)
            self.assertNotIn("do work", command)

    def test_codex_exec_uses_argv_prompt_transport(self):
        adapter = get_runtime_adapter("codex")
        with patch.dict(CONFIG, {"CODEX_CLI_ARGS": "exec --full-auto", "CODEX_PROMPT_TRANSPORT": "argv"}, clear=False):
            self.assertEqual(adapter.prompt_transport(), "argv")
            command = adapter.launch_bootstrap_command("/tmp/project", initial_prompt="ship it")
            self.assertIn("codex exec --full-auto 'ship it'", command)
            self.assertIn("__BISHOPBOT_RUNTIME_EXIT__", command)
            self.assertIn('printf \'%s:%s:%s\\n\'', command)
            self.assertFalse(adapter.supports_interactive_controls())

    def test_launch_bootstrap_command_writes_runtime_state_sidecar_when_configured(self):
        adapter = get_runtime_adapter("codex")
        command = adapter.launch_bootstrap_command(
            "/tmp/project",
            initial_prompt="ship it",
            launch_mode="full-auto",
            state_file="/tmp/session-state/test.state",
        )
        self.assertIn("status=running", command)
        self.assertIn("heartbeat_at=%s", command)
        self.assertIn("started_at=%s", command)
        self.assertIn("status=exited", command)
        self.assertIn("exited_at=%s", command)
        self.assertIn("HEARTBEAT_PID", command)
        self.assertIn("sleep 3", command)
        self.assertIn("/tmp/session-state/test.state", command)
        self.assertIn("__BISHOPBOT_RUNTIME_EXIT__:codex:", command)

    def test_launch_bootstrap_command_can_tee_runtime_output_to_durable_capture(self):
        adapter = get_runtime_adapter("codex")
        command = adapter.launch_bootstrap_command(
            "/tmp/project",
            initial_prompt="ship it",
            launch_mode="full-auto",
            state_file="/tmp/session-state/test.state",
            output_file="/tmp/session-output/test.log",
        )
        self.assertIn("zsh -lc", command)
        self.assertIn(": > /tmp/session-output/test.log", command)
        self.assertIn("tee -a /tmp/session-output/test.log", command)
        self.assertIn("EXIT_CODE=${pipestatus[1]}", command)
        self.assertIn("__BISHOPBOT_RUNTIME_EXIT__:codex:", command)

    def test_codex_inferrs_argv_when_exec_is_used(self):
        adapter = get_runtime_adapter("codex")
        with patch.dict(CONFIG, {"CODEX_CLI_ARGS": "exec --full-auto", "CODEX_PROMPT_TRANSPORT": ""}, clear=False):
            self.assertEqual(adapter.prompt_transport(), "argv")

    def test_codex_full_auto_launch_mode_switches_command_and_transport(self):
        adapter = get_runtime_adapter("codex")
        with patch.dict(
            CONFIG,
            {"CODEX_CLI_ARGS_FULL_AUTO": "exec --full-auto", "CODEX_CLI_ARGS_YOLO": "--yolo"},
            clear=False,
        ):
            self.assertEqual(adapter.launch_command(launch_mode="full-auto"), "codex exec --full-auto")
            self.assertEqual(adapter.launch_command(launch_mode="yolo"), "codex --yolo")
            self.assertEqual(adapter.prompt_transport(launch_mode="full-auto"), "argv")
            self.assertEqual(adapter.prompt_transport(launch_mode="yolo"), "stdin")
            self.assertFalse(adapter.supports_interactive_controls(launch_mode="full-auto"))
            self.assertTrue(adapter.supports_interactive_controls(launch_mode="yolo"))

    def test_parse_runtime_invocation_supports_mode_prefixes(self):
        runtime, mode, remaining = parse_runtime_invocation("codex", "--yolo inspect the repo")
        self.assertEqual(runtime, "codex")
        self.assertEqual(mode, "yolo")
        self.assertEqual(remaining, "inspect the repo")

        runtime, mode, remaining = parse_runtime_invocation("codex", "mode:full-auto ship it")
        self.assertEqual(runtime, "codex")
        self.assertEqual(mode, "full-auto")
        self.assertEqual(remaining, "ship it")

        runtime, mode, remaining = parse_runtime_invocation("gemini", "--shell open the app")
        self.assertEqual(runtime, "gemini")
        self.assertEqual(mode, "yolo")
        self.assertEqual(remaining, "open the app")

    def test_parse_runtime_invocation_supports_runtime_overrides(self):
        runtime, mode, remaining = parse_runtime_invocation("gemini", "runtime:codex --yolo inspect the repo")
        self.assertEqual(runtime, "codex")
        self.assertEqual(mode, "yolo")
        self.assertEqual(remaining, "inspect the repo")

        runtime, mode, remaining = parse_runtime_invocation("codex", "--gemini open the app")
        self.assertEqual(runtime, "gemini")
        self.assertEqual(mode, None)
        self.assertEqual(remaining, "open the app")

    def test_codex_exit_marker_drives_completion_and_error_detection(self):
        adapter = get_runtime_adapter("codex")
        success_output = "work done\n__BISHOPBOT_RUNTIME_EXIT__:codex:0"
        failure_output = "bad news\n__BISHOPBOT_RUNTIME_EXIT__:codex:2"

        self.assertEqual(adapter.extract_exit_code(success_output), 0)
        self.assertTrue(adapter.detect_completion(success_output))
        self.assertFalse(adapter.detect_error(success_output))
        self.assertFalse(adapter.detect_attention_required(success_output))

        self.assertEqual(adapter.extract_exit_code(failure_output), 2)
        self.assertFalse(adapter.detect_completion(failure_output))
        self.assertTrue(adapter.detect_error(failure_output))

    def test_codex_ignores_known_noise_errors_before_success(self):
        adapter = get_runtime_adapter("codex")
        noisy_success_output = (
            "\x1b[31mERROR\x1b[0m failed to load skill /Users/matthewbishop/.agents/skills/foo/SKILL.md\n"
            "ERROR worker quit with fatal: Transport channel closed\n"
            "hello-from-codex\n"
            "__BISHOPBOT_RUNTIME_EXIT__:codex:0"
        )

        self.assertEqual(adapter.sanitize_output(noisy_success_output).splitlines()[0], "ERROR failed to load skill /Users/matthewbishop/.agents/skills/foo/SKILL.md")
        self.assertFalse(adapter.detect_error(noisy_success_output))
        self.assertTrue(adapter.detect_completion(noisy_success_output))

    def test_runtime_progress_markers_are_parsed(self):
        adapter = get_runtime_adapter("codex")
        output = "booting\nTASK 1 COMPLETE\nnoise\nTASK 3 COMPLETE\nSESSION COMPLETE final summary line"
        self.assertEqual(adapter.extract_task_progress(output), 3)
        self.assertEqual(adapter.extract_final_summary(output), "final summary line")

    def test_codex_final_summary_stops_before_footer_noise(self):
        adapter = get_runtime_adapter("codex")
        output = (
            "TASK 1 COMPLETE\n"
            "SESSION COMPLETE live probe ok\n"
            "tokens used\n"
            "33,029\n"
            "ERROR fail to delete session: Client error\n"
        )
        self.assertEqual(adapter.extract_final_summary(output), "live probe ok")
        self.assertFalse(adapter.detect_error(output))

    def test_codex_multiline_summary_ignores_known_noise_and_exit_marker(self):
        adapter = get_runtime_adapter("codex")
        output = (
            "SESSION COMPLETE built listener adapter\n"
            "captured runtime-aware summary\n"
            "ERROR worker quit with fatal: Transport channel closed\n"
            "__BISHOPBOT_RUNTIME_EXIT__:codex:0\n"
        )
        self.assertEqual(
            adapter.extract_final_summary(output),
            "built listener adapter captured runtime-aware summary",
        )

    def test_gemini_legacy_completion_tokens_still_work(self):
        adapter = get_runtime_adapter("gemini")
        output = "all tasks done\nsession complete"
        self.assertTrue(adapter.detect_completion(output))
        self.assertIsNone(adapter.extract_exit_code(output))


if __name__ == "__main__":
    unittest.main()
