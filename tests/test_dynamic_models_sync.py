import pytest
from fastapi.testclient import TestClient
from prime_gate.server import app
from prime_gate.db import db, REC_MODEL, REC_QUOTA
from prime_gate.quota.monitor import QuotaMonitor, build_model_spec
from prime_gate.auth.accounts import AccountManager
from prime_gate.crypto.auth_manager import AuthManager

client = TestClient(app)

class TestDynamicModelsSync:
    """Test suite for dynamic model loading, database persistence, account switching, and zero-hardcoding."""

    def test_01_no_recommended_label_in_db_or_spec(self):
        """Verifies that no models in DB or build_model_spec contain '(Recommended)' in their display name."""
        # Check all models stored across all accounts in SQLite DB
        model_keys = db.list_keys("models:")
        assert len(model_keys) > 0, "Expected at least one account models key in DB"

        for k in model_keys:
            record = db.get(k)
            assert record and "models" in record, f"Expected models list in {k}"
            for m in record["models"]:
                name = m.get("name", "")
                assert "(Recommended)" not in name, f"Forbidden '(Recommended)' found in DB key {k}, model {m['id']}: {name}"

        # Test build_model_spec directly with alias and raw data
        spec = build_model_spec("gemini-3.8-flash", {"name": "Gemini 3.8 Flash (High) (Recommended)"})
        assert "(Recommended)" not in spec["name"]

    def test_02_api_models_endpoint_returns_from_db(self):
        """Verifies that /api/models returns models dynamically stored in SQLite WAL without requiring API key."""
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()

        assert "models" in data
        assert "total" in data
        assert data["total"] > 0
        assert isinstance(data["models"], list)

        for m in data["models"]:
            assert "(Recommended)" not in m.get("name", "")
            assert m.get("object") == "model"

    def test_03_v1_models_allows_session_cookie(self):
        """Verifies that /v1/models works with session cookie (dashboard UI) and returns valid model list."""
        session_id, _ = AuthManager.create_session()
        
        # Request with session cookie
        resp = client.get("/v1/models", cookies={"pg_session": session_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

        for m in data["data"]:
            assert "(Recommended)" not in m.get("name", "")

    def test_04_fallback_to_account_in_db(self):
        """Verifies that get_available_models prioritizes models:{email} from database."""
        mgr = AccountManager()
        active_acc = mgr.get_active_account()
        assert active_acc is not None
        email = active_acc["email"]

        # Ensure active account has models in DB
        db_models = db.get(f"models:{email}")
        assert db_models is not None and "models" in db_models

        resolved = QuotaMonitor.get_available_models(active_acc)
        assert len(resolved) == len(db_models["models"])
        resolved_ids = {m["id"] for m in resolved}
        db_ids = {m["id"] for m in db_models["models"]}
        assert resolved_ids == db_ids

    def test_05_account_switch_refreshes_data(self):
        """Verifies that switching accounts updates active account, models, and quotas."""
        mgr = AccountManager()
        accounts = mgr.load_accounts()
        if len(accounts) >= 2:
            current_active = mgr.get_active_account()["email"]
            target_account = [a["email"] for a in accounts if a["email"] != current_active][0]

            resp = client.post(f"/api/accounts/switch?email={target_account}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["active_account"] == target_account
            assert "models" in data
            assert "quota" in data

            # Verify active account switched
            assert mgr.get_active_account()["email"] == target_account

            # Switch back to original
            client.post(f"/api/accounts/switch?email={current_active}")
            assert mgr.get_active_account()["email"] == current_active
