import unittest
from starlette.testclient import TestClient
from prime_gate.server import app
from prime_gate.db import db
from prime_gate.crypto.auth_manager import AuthManager, COOKIE_SESSION_NAME, HEADER_CSRF_NAME, _ACTIVE_SESSIONS


class TestDashboardSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, base_url="http://localhost:52111")
        cls.raw_key, cls.key_rec = db.create_api_key(name="dashboard-test-key")

    @classmethod
    def tearDownClass(cls):
        db.revoke_api_key(cls.key_rec["id"])

    def setUp(self):
        # Reset rate limiting state before each test
        AuthManager.record_login_attempt("127.0.0.1", True)
        AuthManager.record_login_attempt("testclient", True)

    def test_dns_rebinding_mitigation_host_header(self):
        # Host header from an attacker domain must be rejected with 403 Forbidden
        resp = self.client.get(
            "/api/auth/session/status",
            headers={"Host": "attacker.com"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("invalid_host", resp.text)

    def test_security_headers_present(self):
        resp = self.client.get("/api/auth/session/status")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("Content-Security-Policy", resp.headers)
        self.assertIn("frame-ancestors 'none'", resp.headers["Content-Security-Policy"])

    def test_unauthorized_origin_mutation_rejected(self):
        # State-changing request with external malicious origin header
        resp = self.client.post(
            "/api/system/restart",
            headers={"Origin": "https://malicious-website.com"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("invalid_origin", resp.text)

    def test_session_login_and_csrf_protection(self):
        # 1. Login with API key
        login_resp = self.client.post(
            "/api/auth/session",
            json={"api_key": self.raw_key}
        )
        self.assertEqual(login_resp.status_code, 200)
        data = login_resp.json()
        self.assertTrue(data["success"])
        csrf_token = data["csrf_token"]
        self.assertIsNotNone(csrf_token)

        # 2. Check session status
        status_resp = self.client.get("/api/auth/session/status")
        self.assertEqual(status_resp.status_code, 200)
        self.assertTrue(status_resp.json()["authenticated"])

        # 3. State-changing request WITHOUT CSRF header must be rejected
        fail_mut = self.client.post("/api/db/optimize")
        self.assertEqual(fail_mut.status_code, 403)
        self.assertIn("csrf_validation_failed", fail_mut.text)

        # 4. State-changing request WITH matching CSRF header must succeed
        ok_mut = self.client.post(
            "/api/db/optimize",
            headers={"x-csrf-token": csrf_token}
        )
        self.assertEqual(ok_mut.status_code, 200)

        # 5. Logout
        logout_resp = self.client.post("/api/auth/session/logout")
        self.assertEqual(logout_resp.status_code, 200)

        # Session is now invalid
        status_after = self.client.get("/api/auth/session/status")
        self.assertFalse(status_after.json()["authenticated"])

    def test_rate_limiting_on_failed_logins(self):
        # Use a distinct client instance for rate limit isolation
        rate_client = TestClient(app, base_url="http://localhost:52111")
        ip = "127.0.0.1"
        AuthManager.record_login_attempt(ip, True)  # reset IP

        for _ in range(5):
            rate_client.post("/api/auth/session", json={"api_key": "wrong_key_attempt"})

        # 6th attempt must be locked out with HTTP 429
        blocked = rate_client.post("/api/auth/session", json={"api_key": "any_key"})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("rate_limit_error", blocked.text)

        # Clean up rate limit state for test teardown
        AuthManager.record_login_attempt(ip, True)

    def test_permanent_session_persistence_across_memory_wipe(self):
        """Verifies session survives daemon/server restart (memory wipe) via SQLite DB."""
        # 1. Login to get cookies
        login_resp = self.client.post(
            "/api/auth/session",
            json={"api_key": self.raw_key}
        )
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(COOKIE_SESSION_NAME, self.client.cookies)
        session_id = self.client.cookies[COOKIE_SESSION_NAME]

        # 2. Verify cookie max_age is set to 10 years (315360000 seconds)
        set_cookie_header = login_resp.headers.get("set-cookie", "")
        self.assertIn("max-age=315360000", set_cookie_header.lower())

        # 3. Simulate server restart: completely clear in-memory sessions dictionary
        _ACTIVE_SESSIONS.clear()
        self.assertEqual(len(_ACTIVE_SESSIONS), 0)

        # 4. Status endpoint should rehydrate session from persistent DB
        status_resp = self.client.get("/api/auth/session/status")
        self.assertEqual(status_resp.status_code, 200)
        self.assertTrue(status_resp.json()["authenticated"])
        self.assertIsNotNone(status_resp.json()["csrf_token"])

        # 5. AuthManager memory cache should now have restored the session
        self.assertIn(session_id, _ACTIVE_SESSIONS)


if __name__ == "__main__":
    unittest.main()
