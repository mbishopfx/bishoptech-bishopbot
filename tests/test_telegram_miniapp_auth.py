import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

from bishop_meta.telegram_miniapp_auth import validate_telegram_init_data


class TelegramMiniAppAuthTests(unittest.TestCase):
    def _make_init_data(self, bot_token: str, user_id: int, auth_date: int | None = None) -> str:
        auth_date = auth_date or int(time.time())
        payload = {
            'auth_date': str(auth_date),
            'query_id': 'AAHdF6IQAAAAANjv9Yy3',
            'user': json.dumps({'id': user_id, 'first_name': 'Matthew', 'username': 'bishopbot', 'language_code': 'en'}),
        }
        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(payload.items()))
        secret_key = hmac.new(b'WebAppData', bot_token.encode('utf-8'), hashlib.sha256).digest()
        payload['hash'] = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return urlencode(payload)

    def test_validate_telegram_init_data_accepts_valid_payload(self):
        bot_token = '123456:ABCDEF'
        init_data = self._make_init_data(bot_token, 1992876655)
        result = validate_telegram_init_data(
            init_data,
            bot_token=bot_token,
            allowed_user_ids=[1992876655],
            owner_id=1992876655,
            max_age_seconds=86400,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.user_id, 1992876655)

    def test_validate_telegram_init_data_rejects_unauthorized_user(self):
        bot_token = '123456:ABCDEF'
        init_data = self._make_init_data(bot_token, 111)
        result = validate_telegram_init_data(
            init_data,
            bot_token=bot_token,
            allowed_user_ids=[222],
            owner_id=333,
            max_age_seconds=86400,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, 'user not allowed')

    def test_validate_telegram_init_data_rejects_bad_signature(self):
        bot_token = '123456:ABCDEF'
        init_data = self._make_init_data(bot_token, 1992876655)
        tampered = init_data.replace('bishopbot', 'bishopbot2')
        result = validate_telegram_init_data(
            tampered,
            bot_token=bot_token,
            allowed_user_ids=[1992876655],
            owner_id=1992876655,
            max_age_seconds=86400,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, 'signature mismatch')


if __name__ == '__main__':
    unittest.main()
