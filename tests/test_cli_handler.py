import unittest
from unittest.mock import patch

from handlers import cli_handler


class CliHandlerTests(unittest.TestCase):
    @patch("handlers.cli_handler.TerminalSessionManager.start_session", return_value="sess-1234")
    @patch("handlers.cli_handler.reply_service.send")
    @patch("handlers.cli_handler.TaskPlanner.build_cli_prompt", return_value="runtime prompt")
    @patch("handlers.cli_handler.TaskPlanner.build_plan_summary", return_value="summary")
    @patch("handlers.cli_handler.TaskPlanner.plan_tasks", return_value=("1. Inspect repo", ["Inspect repo"]))
    @patch("handlers.cli_handler.openai_service.process_message", return_value="Inspect repo")
    def test_cli_handler_allows_runtime_override_from_cli_command(
        self,
        mock_process,
        mock_plan,
        mock_summary,
        mock_prompt,
        mock_reply,
        mock_start_session,
    ):
        result = cli_handler.handle_cli_command(
            "runtime:codex --yolo inspect the listener",
            response_url="https://example.com/slack",
            user_id="U123",
            mode="gemini",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["session_id"], "sess-1234")
        mock_plan.assert_called_once_with("Inspect repo", mode="codex")
        mock_prompt.assert_not_called()
        mock_start_session.assert_called_once()
        _, kwargs = mock_start_session.call_args
        self.assertEqual(kwargs["agent_mode"], "codex")
        self.assertEqual(kwargs["launch_mode"], "yolo")
        self.assertEqual(kwargs["initial_command"], "inspect the listener")
        self.assertIn("Runtime override: *Codex*", mock_reply.call_args.args[1])

    @patch("handlers.cli_handler.TerminalSessionManager.start_session", return_value="sess-gemini")
    @patch("handlers.cli_handler.reply_service.send")
    @patch("handlers.cli_handler.TaskPlanner.build_cli_prompt", return_value="runtime prompt")
    @patch("handlers.cli_handler.TaskPlanner.build_plan_summary", return_value="summary")
    @patch("handlers.cli_handler.TaskPlanner.plan_tasks", return_value=("1. Check weather", ["Check weather"]))
    @patch("handlers.cli_handler.openai_service.process_message", return_value="Check the weather in Carthage, MO")
    def test_cli_handler_uses_original_slack_text_for_gemini_stdin_sessions(
        self,
        mock_process,
        mock_plan,
        mock_summary,
        mock_prompt,
        mock_reply,
        mock_start_session,
    ):
        result = cli_handler.handle_cli_command(
            "check the current weather in Carthage, MO",
            response_url="https://example.com/slack",
            user_id="U123",
            mode="gemini",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["session_id"], "sess-gemini")
        mock_prompt.assert_not_called()
        _, kwargs = mock_start_session.call_args
        self.assertEqual(kwargs["agent_mode"], "gemini")
        self.assertEqual(kwargs["initial_command"], "check the current weather in Carthage, MO")


if __name__ == "__main__":
    unittest.main()
