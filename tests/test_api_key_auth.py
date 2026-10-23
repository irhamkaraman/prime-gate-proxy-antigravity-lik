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
        # Permanently clean up test key
        db.delete_api_key(cls.key_record["id"])

    def setUp(self):
        # Ensure fresh client state without lingering session cookies
        self.client.cookies.clear()

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
        try:
            # Verify it works
            resp = self.client.get("/v1/models", headers={"Authorization": f"Bearer {raw_temp}"})
            self.assertEqual(resp.status_code, 200)

            # Revoke it
            db.revoke_api_key(temp_rec["id"])

            # Must now fail
            resp2 = self.client.get("/v1/models", headers={"Authorization": f"Bearer {raw_temp}"})
            self.assertEqual(resp2.status_code, 401)
        finally:
            db.delete_api_key(temp_rec["id"])

    def test_bulk_revoke_and_delete_api_keys(self):
        # 1. Login to establish dashboard session
        login_res = self.client.post("/api/auth/session", json={"api_key": self.raw_key})
        self.assertEqual(login_res.status_code, 200)
        csrf_token = login_res.json()["csrf_token"]
        headers = {"x-csrf-token": csrf_token}

        # 2. Create 3 temporary test keys
        k1_raw, k1 = db.create_api_key(name="bulk-test-1")
        k2_raw, k2 = db.create_api_key(name="bulk-test-2")
        k3_raw, k3 = db.create_api_key(name="bulk-test-3")
        ids = [k1["id"], k2["id"], k3["id"]]

        try:
            # 3. Test bulk revoke
            rev_resp = self.client.post("/api/auth/keys/bulk-revoke", json={"ids": ids}, headers=headers)
            self.assertEqual(rev_resp.status_code, 200)
            self.assertEqual(rev_resp.json()["revoked_count"], 3)

            # 4. Verify all are revoked
            all_keys = {k["id"]: k for k in db.list_api_keys()}
            for kid in ids:
                self.assertIsNotNone(all_keys[kid]["revoked_at"])

            # 5. Test bulk delete
            del_resp = self.client.post("/api/auth/keys/bulk-delete", json={"ids": ids}, headers=headers)
            self.assertEqual(del_resp.status_code, 200)
            self.assertEqual(del_resp.json()["deleted_count"], 3)

            # 6. Verify all are deleted from database
            remaining_ids = [k["id"] for k in db.list_api_keys()]
            for kid in ids:
                self.assertNotIn(kid, remaining_ids)
        finally:
            # Teardown safety
            db.delete_api_keys(ids)

    def test_pagination_and_search_api_keys(self):
        # 1. Login to establish dashboard session
        login_res = self.client.post("/api/auth/session", json={"api_key": self.raw_key})
        self.assertEqual(login_res.status_code, 200)

        # 2. Test pagination params
        resp = self.client.get("/api/auth/keys?page=1&limit=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("keys", data)
        self.assertIn("total", data)
        self.assertIn("page", data)
        self.assertIn("limit", data)
        self.assertIn("total_pages", data)
        self.assertLessEqual(len(data["keys"]), 2)

        # 3. Test search filter
        search_resp = self.client.get("/api/auth/keys?search=unit-test-key")
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.json()
        self.assertTrue(any(k["name"] == "unit-test-key" for k in search_data["keys"]))


if __name__ == "__main__":
    unittest.main()
