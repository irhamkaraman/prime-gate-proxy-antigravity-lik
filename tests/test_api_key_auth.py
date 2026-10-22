import unittest
from starlette.testclient import TestClient
from prime_gate.server import app
from prime_gate.db import db
from prime_gate.crypto.auth_manager import AuthManager


class TestAPIKeyAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, base_url="http://localhost:52111")
        # Create an authorized test API key
        cls.raw_key, cls.key_record = db.create_api_key(name="unit-test-key")

    @classmethod
    def tearDownClass(cls):
        # Revoke test key
        db.revoke_api_key(cls.key_record["id"])

    def test_proxy_models_rejected_without_api_key(self):
        resp = self.client.get("/v1/models")
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "missing_api_key")

    def test_proxy_models_accepted_with_bearer_token(self):
        resp = self.client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {self.raw_key}"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_proxy_models_accepted_with_x_api_key_header(self):
        resp = self.client.get(
            "/v1/models",
            headers={"x-api-key": self.raw_key}
        )
        self.assertEqual(resp.status_code, 200)

    def test_proxy_models_rejected_with_invalid_key(self):
        resp = self.client.get(
            "/v1/models",
            headers={"Authorization": "Bearer pg-live-invalid0000000000000000000000"}
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "invalid_api_key")

    def test_revoked_key_rejected(self):
        raw_temp, temp_rec = db.create_api_key(name="temp-revoked-key")
        # Verify it works
        resp = self.client.get("/v1/models", headers={"Authorization": f"Bearer {raw_temp}"})
        self.assertEqual(resp.status_code, 200)

        # Revoke it
        db.revoke_api_key(temp_rec["id"])

        # Must now fail
        resp2 = self.client.get("/v1/models", headers={"Authorization": f"Bearer {raw_temp}"})
        self.assertEqual(resp2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
