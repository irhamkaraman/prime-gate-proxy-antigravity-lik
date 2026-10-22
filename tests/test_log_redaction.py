import unittest
from prime_gate.logging.redactor import Redactor


class TestLogRedaction(unittest.TestCase):
    def test_oauth_token_redaction(self):
        log_entry = "Received token ya29.a0AWY7Ckl0123456789abcdef from Google OAuth exchange"
        masked = Redactor.mask_string(log_entry)
        self.assertNotIn("ya29.a0AWY7Ckl0123456789abcdef", masked)
        self.assertIn("ya29.[REDACTED_OAUTH_TOKEN]", masked)

    def test_refresh_token_redaction(self):
        log_entry = "Persisting refresh token: 1//04ABCxyz_secret_9999 for user account"
        masked = Redactor.mask_string(log_entry)
        self.assertNotIn("1//04ABCxyz_secret_9999", masked)
        self.assertIn("1//[REDACTED_REFRESH_TOKEN]", masked)

    def test_api_key_redaction(self):
        log_entry = "Request received with key pg-live-abcdef0123456789abcdef0123456789"
        masked = Redactor.mask_string(log_entry)
        self.assertNotIn("abcdef0123456789abcdef0123456789", masked)
        self.assertIn("pg-live-[REDACTED_API_KEY]", masked)

    def test_authorization_bearer_header_redaction(self):
        log_entry = "Headers: Authorization: Bearer secret_bearer_token_123456"
        masked = Redactor.mask_string(log_entry)
        self.assertNotIn("secret_bearer_token_123456", masked)
        self.assertIn("Bearer [REDACTED_BEARER]", masked)

    def test_cookie_session_redaction(self):
        log_entry = "Cookie: pg_session=my_secret_session_token_12345; Path=/"
        masked = Redactor.mask_string(log_entry)
        self.assertNotIn("my_secret_session_token_12345", masked)
        self.assertIn("pg_session=[REDACTED_SESSION]", masked)

    def test_recursive_object_redaction(self):
        data = {
            "email": "user@example.com",
            "refreshToken": "1//secret_token",
            "access_token": "ya29.secret_access",
            "nested": {
                "key_hash": "a1b2c3d4",
                "salt": "secret_salt_value",
                "normal_field": "public_data"
            },
            "list_items": [
                {"token": "ya29.another_secret", "name": "item1"}
            ]
        }
        masked = Redactor.mask_object(data)
        self.assertEqual(masked["refreshToken"], "[REDACTED]")
        self.assertEqual(masked["access_token"], "[REDACTED]")
        self.assertEqual(masked["nested"]["key_hash"], "[REDACTED]")
        self.assertEqual(masked["nested"]["salt"], "[REDACTED]")
        self.assertEqual(masked["nested"]["normal_field"], "public_data")
        self.assertEqual(masked["list_items"][0]["token"], "[REDACTED]")
        self.assertEqual(masked["list_items"][0]["name"], "item1")


if __name__ == "__main__":
    unittest.main()
