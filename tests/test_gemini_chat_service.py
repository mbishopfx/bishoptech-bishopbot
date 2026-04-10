import unittest
from unittest.mock import MagicMock, patch

from services import gemini_chat_service


class GeminiChatServiceTests(unittest.TestCase):
    @patch("services.gemini_chat_service.agent_context_service.build_prompt_context", return_value="persistent context")
    def test_build_system_prompt_mentions_non_terminal_chat_and_context(self, mock_context):
        prompt = gemini_chat_service.build_system_prompt()
        self.assertIn("lightweight Slack brainstorming assistant", prompt)
        self.assertIn("not the terminal execution path", prompt)
        self.assertIn("persistent context", prompt)

    @patch("services.gemini_chat_service.CONFIG", {"GEMINI_API_KEY": "test-key", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "OPENAI_API_KEY": None})
    @patch("services.gemini_chat_service.agent_context_service.build_prompt_context", return_value="persistent context")
    @patch("services.gemini_chat_service.requests.post")
    def test_generate_chat_reply_uses_gemini_rest_api(self, mock_post, mock_context):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"candidates": [{"content": {"parts": [{"text": "brainstorm answer"}]}}]}),
        )

        output = gemini_chat_service.generate_chat_reply("help me brainstorm", user_id="U123")

        self.assertEqual(output, "brainstorm answer")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("gemini-2.5-flash:generateContent", args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")
        self.assertIn("persistent context", kwargs["json"]["system_instruction"]["parts"][0]["text"])

    @patch("services.gemini_chat_service.CONFIG", {"GEMINI_API_KEY": "test-key", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "OPENAI_API_KEY": "openai-test", "MENTION_CHAT_OPENAI_FALLBACK_MODEL": "gpt-4o-mini"})
    @patch("services.gemini_chat_service.agent_context_service.build_prompt_context", return_value="persistent context")
    @patch("services.gemini_chat_service.openai_service.generate_response", return_value="fallback answer")
    @patch("services.gemini_chat_service._generate_via_gemini_cli", side_effect=RuntimeError("cli unavailable"))
    @patch("services.gemini_chat_service.requests.post")
    def test_generate_chat_reply_falls_back_to_openai_when_gemini_is_denied(self, mock_post, mock_cli, mock_openai, mock_context):
        mock_post.return_value = MagicMock(
            status_code=403,
            json=MagicMock(return_value={"error": {"message": "Your project has been denied access."}}),
            text='{"error":{"message":"Your project has been denied access."}}',
        )

        output = gemini_chat_service.generate_chat_reply("help me brainstorm", user_id="U123")

        self.assertIn("OpenAI fallback", output)
        self.assertIn("fallback answer", output)
        mock_openai.assert_called_once()
        _, kwargs = mock_openai.call_args
        self.assertEqual(kwargs["model"], "gpt-4o-mini")

    @patch("services.gemini_chat_service.CONFIG", {"GEMINI_API_KEY": "test-key", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "OPENAI_API_KEY": "openai-test", "MENTION_CHAT_OPENAI_FALLBACK_MODEL": "gpt-4o-mini"})
    @patch("services.gemini_chat_service.agent_context_service.build_prompt_context", return_value="persistent context")
    @patch("services.gemini_chat_service._generate_via_gemini_cli", return_value="cli fallback answer")
    @patch("services.gemini_chat_service.requests.post")
    def test_generate_chat_reply_falls_back_to_local_gemini_cli_when_api_is_denied(self, mock_post, mock_cli, mock_context):
        mock_post.return_value = MagicMock(
            status_code=403,
            json=MagicMock(return_value={"error": {"message": "Your project has been denied access."}}),
            text='{"error":{"message":"Your project has been denied access."}}',
        )

        output = gemini_chat_service.generate_chat_reply("help me brainstorm", user_id="U123")

        self.assertIn("signed-in local Gemini CLI", output)
        self.assertIn("cli fallback answer", output)
        mock_cli.assert_called_once()

    @patch("services.gemini_chat_service.CONFIG", {"GEMINI_API_KEY": "test-key", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "OPENAI_API_KEY": None})
    @patch("services.gemini_chat_service.agent_context_service.build_prompt_context", return_value="persistent context")
    @patch("services.gemini_chat_service._generate_via_gemini_cli", side_effect=RuntimeError("cli unavailable"))
    @patch("services.gemini_chat_service.requests.post")
    def test_generate_chat_reply_returns_friendlier_error_without_fallback(self, mock_post, mock_cli, mock_context):
        mock_post.return_value = MagicMock(
            status_code=403,
            json=MagicMock(return_value={"error": {"message": "Your project has been denied access."}}),
            text='{"error":{"message":"Your project has been denied access."}}',
        )

        with self.assertRaises(RuntimeError) as exc:
            gemini_chat_service.generate_chat_reply("help me brainstorm", user_id="U123")

        self.assertIn("Gemini mention chat is unavailable for the current API key or Google project", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
