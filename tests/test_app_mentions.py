import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class AppMentionTests(unittest.TestCase):
    def test_app_boot_registers_app_mention_handler(self):
        fake_app_instance = MagicMock()

        def command_decorator(_name):
            def _register(func):
                return func
            return _register

        def action_decorator(_name):
            def _register(func):
                return func
            return _register

        event_handlers = {}

        def event_decorator(name):
            def _register(func):
                event_handlers[name] = func
                return func
            return _register

        fake_app_instance.command.side_effect = command_decorator
        fake_app_instance.action.side_effect = action_decorator
        fake_app_instance.event.side_effect = event_decorator
        fake_app_instance.client.auth_test.return_value = {"user_id": "U_BOT"}

        fake_slack_bolt = types.ModuleType("slack_bolt")
        fake_slack_bolt.App = MagicMock(return_value=fake_app_instance)
        fake_socket_mode_module = types.ModuleType("slack_bolt.adapter.socket_mode")
        fake_socket_mode_module.SocketModeHandler = MagicMock()
        fake_adapter_module = types.ModuleType("slack_bolt.adapter")
        fake_adapter_module.socket_mode = fake_socket_mode_module
        fake_redis_module = types.ModuleType("redis")
        fake_redis_module.Redis = MagicMock()
        fake_redis_module.Redis.from_url = MagicMock()
        fake_rq_module = types.ModuleType("rq")
        fake_rq_module.Queue = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "slack_bolt": fake_slack_bolt,
                "slack_bolt.adapter": fake_adapter_module,
                "slack_bolt.adapter.socket_mode": fake_socket_mode_module,
                "redis": fake_redis_module,
                "rq": fake_rq_module,
            },
        ), patch.dict(
            "config.CONFIG",
            {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_APP_TOKEN": "xapp-test", "REDIS_URL": "redis://localhost:6379/0"},
            clear=False,
        ):
            module = importlib.import_module("app")
            module = importlib.reload(module)
            module._start_slack_socket_mode()

        self.assertIn("app_mention", event_handlers)


if __name__ == "__main__":
    unittest.main()
