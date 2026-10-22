import json
import logging
import time
import unittest
from fastapi.testclient import TestClient
from prime_gate.server import app
from prime_gate.metrics import PrometheusMetrics, metrics
from prime_gate.logging.redactor import RedactingJsonFormatter, Redactor

class TestObservability(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_x_request_id_tracing_generated(self):
        """Verifies incoming requests without X-Request-ID receive a generated UUID tracing header."""
        res = self.client.get("/health/liveness")
        self.assertEqual(res.status_code, 200)
        self.assertIn("x-request-id", res.headers)
        self.assertTrue(len(res.headers["x-request-id"]) >= 16)

    def test_x_request_id_tracing_propagated(self):
        """Verifies caller-provided X-Request-ID is propagated through response."""
        custom_id = "trace-test-custom-id-9988"
        res = self.client.get("/health/liveness", headers={"X-Request-ID": custom_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("x-request-id"), custom_id)

    def test_health_endpoints_and_probes(self):
        """Verifies /health, /health/liveness, and /health/readiness contract."""
        # Liveness
        res_live = self.client.get("/health/liveness")
        self.assertEqual(res_live.status_code, 200)
        live_json = res_live.json()
        self.assertEqual(live_json.get("status"), "ok")
        self.assertIn("uptime_seconds", live_json)

        # Readiness
        res_ready = self.client.get("/health/readiness")
        self.assertIn(res_ready.status_code, [200, 503])
        ready_json = res_ready.json()
        self.assertIn("status", ready_json)
        self.assertIn("active_accounts", ready_json)

        # Main /health includes both liveness and readiness sections
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        h_json = res_health.json()
        self.assertIn("liveness", h_json)
        self.assertIn("readiness", h_json)

    def test_prometheus_metrics_endpoint(self):
        """Verifies /metrics returns valid Prometheus exposition text with required metric keys."""
        # Record a test event
        metrics.record_request("openai", "gemini-2.5-flash", 200, 0.45, ttft_seconds=0.12)
        metrics.record_tokens(prompt=120, completion=80, reasoning=20, saved=50)
        metrics.record_cache_hit("exact")
        metrics.record_cache_miss()
        metrics.record_failover()
        metrics.record_compactor_saved(45)

        res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/plain", res.headers.get("content-type", ""))
        text = res.text

        # Verify all mandatory metric names from specification
        self.assertIn("primegate_requests_total", text)
        self.assertIn("primegate_request_duration_seconds", text)
        self.assertIn("primegate_time_to_first_token_seconds", text)
        self.assertIn("primegate_tokens_total", text)
        self.assertIn("primegate_cache_hits_total", text)
        self.assertIn("primegate_cache_misses_total", text)
        self.assertIn("primegate_active_accounts", text)
        self.assertIn("primegate_account_failovers_total", text)
        self.assertIn("primegate_compactor_tokens_saved_total", text)

    def test_structured_json_logging_redaction(self):
        """Verifies RedactingJsonFormatter emits valid JSON and scrubs credentials."""
        formatter = RedactingJsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="User ya29.a0AfH6SMSECRET token connected with key pg-live-abc1234567890123456",
            args=(),
            exc_info=None
        )
        record.request_id = "req-123456"

        formatted = formatter.format(record)
        data = json.loads(formatted)

        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test_logger")
        self.assertEqual(data["request_id"], "req-123456")
        self.assertIn("timestamp", data)
        # Verify secret redaction inside JSON string
        self.assertNotIn("ya29.a0AfH6SMSECRET", data["message"])
        self.assertNotIn("pg-live-abc1234567890123456", data["message"])
        self.assertIn("[REDACTED_OAUTH_TOKEN]", data["message"])
        self.assertIn("[REDACTED_API_KEY]", data["message"])

if __name__ == "__main__":
    unittest.main()
