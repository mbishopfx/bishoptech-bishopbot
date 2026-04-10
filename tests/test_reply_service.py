import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from services import reply_service


class ReplyServiceTests(unittest.TestCase):
    def test_console_target_streams_to_stdout(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            ok = reply_service.send("console:smoke", "hello local world")

        self.assertTrue(ok)
        output = buffer.getvalue()
        self.assertIn("console:smoke", output)
        self.assertIn("hello local world", output)

    @patch("services.reply_service.slack_service.send_delayed_message", return_value=True)
    def test_non_console_target_still_routes_to_slack(self, mock_slack_send):
        ok = reply_service.send("https://example.com/slack", "hello slack")
        self.assertTrue(ok)
        mock_slack_send.assert_called_once_with("https://example.com/slack", "hello slack", blocks=None)


if __name__ == "__main__":
    unittest.main()
