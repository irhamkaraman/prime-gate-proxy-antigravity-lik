import time
import json
import pytest
from fastapi.testclient import TestClient

from prime_gate.server import app, compute_cache_key
from prime_gate.db import db
from prime_gate.security.rate_limiter import KeyRateLimiter


@pytest.fixture
def client():
    return TestClient(app)


def test_rpm_limit_exceeded_returns_429_openai(client):
    """Verifies that exceeding the RPM limit on OpenAI endpoints returns 429 with Retry-After and OpenAI error JSON."""
    raw_key, record = db.create_api_key(
        name="test-rpm-openai",
        rate_limit_rpm=2
    )
    key_id = record["id"]
    KeyRateLimiter._rpm_timestamps.pop(key_id, None)

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": "ping"}],
        "cache": False
    }

    # Request 1
    r1 = client.post("/v1/chat/completions", headers=headers, json=body)
    assert r1.status_code != 429

    # Request 2
    r2 = client.post("/v1/chat/completions", headers=headers, json=body)
    assert r2.status_code != 429

    # Request 3 -> Exceeds RPM limit of 2
    r3 = client.post("/v1/chat/completions", headers=headers, json=body)
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    assert int(r3.headers["Retry-After"]) >= 1

    err_json = r3.json()
    assert "error" in err_json
    assert err_json["error"]["type"] == "rate_limit_error"
    assert err_json["error"]["code"] == "rate_limit_exceeded"
    assert "requests per minute reached" in err_json["error"]["message"]


def test_rpm_limit_exceeded_returns_429_anthropic(client):
    """Verifies that exceeding the RPM limit on Anthropic endpoints returns 429 with Anthropic error JSON."""
    raw_key, record = db.create_api_key(
        name="test-rpm-anthropic",
        rate_limit_rpm=1
    )
    key_id = record["id"]
    KeyRateLimiter._rpm_timestamps.pop(key_id, None)

    headers = {
        "x-api-key": raw_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    body = {
        "model": "claude-3-7-sonnet",
        "messages": [{"role": "user", "content": "ping"}],
        "cache": False
    }

    # Request 1 -> passes limiter
    r1 = client.post("/v1/messages", headers=headers, json=body)
    assert r1.status_code != 429

    # Request 2 -> Exceeds RPM limit of 1
    r2 = client.post("/v1/messages", headers=headers, json=body)
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers

    err_json = r2.json()
    assert err_json.get("type") == "error"
    assert err_json["error"]["type"] == "rate_limit_error"
    assert "requests per minute reached" in err_json["error"]["message"]


def test_sliding_window_reset_allows_requests(client):
    """Verifies that once the 60s sliding window passes, the client can make requests again."""
    raw_key, record = db.create_api_key(
        name="test-sliding-window",
        rate_limit_rpm=1
    )
    key_id = record["id"]

    # Inject an expired timestamp from 70 seconds ago
    KeyRateLimiter._rpm_timestamps[key_id].clear()
    KeyRateLimiter._rpm_timestamps[key_id].append(time.time() - 70.0)

    err = KeyRateLimiter.check_limits(record, "/v1/chat/completions")
    assert err is None


def test_tpd_limit_exceeded_blocks_next_request(client):
    """Verifies that exceeding the daily token limit (TPD) returns 429 with Retry-After header."""
    raw_key, record = db.create_api_key(
        name="test-tpd-limit",
        rate_limit_tpd=500
    )
    key_id = record["id"]

    # Record 600 tokens used today for this key
    db.record_api_key_tokens(
        key_id=key_id,
        prompt_tokens=400,
        completion_tokens=200,
        model="gemini-2.5-flash"
    )

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": "test tpd"}],
        "cache": False
    }

    resp = client.post("/v1/chat/completions", headers=headers, json=body)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers

    err_json = resp.json()
    assert "Daily token limit reached" in err_json["error"]["message"]


def test_disallowed_model_returns_403_openai(client):
    """Verifies that requesting a model not in allowed_models returns 403 Forbidden (OpenAI format)."""
    raw_key, record = db.create_api_key(
        name="test-whitelist-openai",
        allowed_models=json.dumps(["gemini-2.5-flash"])
    )

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gemini-2.5-pro",
        "messages": [{"role": "user", "content": "test"}]
    }

    resp = client.post("/v1/chat/completions", headers=headers, json=body)
    assert resp.status_code == 403

    err_json = resp.json()
    assert "error" in err_json
    assert err_json["error"]["type"] == "invalid_request_error"
    assert err_json["error"]["code"] == "model_not_allowed"
    assert "not permitted for API key" in err_json["error"]["message"]


def test_disallowed_model_returns_403_anthropic(client):
    """Verifies that requesting a model not in allowed_models returns 403 Forbidden (Anthropic format)."""
    raw_key, record = db.create_api_key(
        name="test-whitelist-anthropic",
        allowed_models=json.dumps(["claude-3-5-haiku"])
    )

    headers = {
        "x-api-key": raw_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    body = {
        "model": "claude-3-7-sonnet",
        "messages": [{"role": "user", "content": "test"}]
    }

    resp = client.post("/v1/messages", headers=headers, json=body)
    assert resp.status_code == 403

    err_json = resp.json()
    assert err_json.get("type") == "error"
    assert err_json["error"]["type"] == "permission_error"
    assert "not permitted for API key" in err_json["error"]["message"]


def test_revoked_key_returns_401(client):
    """Verifies that a revoked API key is immediately blocked with 401 Unauthorized."""
    raw_key, record = db.create_api_key(name="test-revoked")
    key_id = record["id"]

    assert db.revoke_api_key(key_id) is True

    headers = {"Authorization": f"Bearer {raw_key}"}
    resp = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gemini-2.5-flash", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert resp.status_code == 401


def test_cache_scope_key_isolation():
    """Verifies that cache_scope='key' isolates the cache key namespace per client key ID."""
    _, key1 = db.create_api_key(name="client-1", cache_scope="key")
    _, key2 = db.create_api_key(name="client-2", cache_scope="key")

    assert key1["id"] != key2["id"]

    k1, _, _, _, _, scope1, _ = compute_cache_key(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "shared prompt"}],
        api_key_prefix=f"key_{key1['id']}"
    )

    k2, _, _, _, _, scope2, _ = compute_cache_key(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "shared prompt"}],
        api_key_prefix=f"key_{key2['id']}"
    )

    assert scope1.startswith(f"key_{key1['id']}")
    assert scope2.startswith(f"key_{key2['id']}")
    assert scope1 != scope2
    assert k1 != k2
