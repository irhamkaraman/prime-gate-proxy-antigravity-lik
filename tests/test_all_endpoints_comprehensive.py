import json
import time
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from prime_gate.server import app
from prime_gate.db import db
from prime_gate.sentinel.loop_guard import AgentLoopGuard

class TestAllEndpointsComprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        res = db.create_api_key("e2e-test-key")
        cls.api_key = res[0] if isinstance(res, tuple) else res.get("raw_key")
        rec = res[1] if isinstance(res, tuple) else res.get("key", {})
        cls.key_id = rec.get("id")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "key_id") and cls.key_id:
            db.delete_api_key(cls.key_id)

    def test_01_health_and_probes(self):
        """1. Comprehensive testing of /health, /health/liveness, /health/readiness."""
        # Liveness
        res_live = self.client.get("/health/liveness")
        self.assertEqual(res_live.status_code, 200)
        self.assertEqual(res_live.json().get("status"), "ok")
        self.assertIn("x-request-id", res_live.headers)

        # Readiness
        res_ready = self.client.get("/health/readiness")
        self.assertIn(res_ready.status_code, [200, 503])
        self.assertIn("active_accounts", res_ready.json())

        # Root Health
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        h_data = res_health.json()
        self.assertIn("liveness", h_data)
        self.assertIn("readiness", h_data)
        self.assertIn("models_health", h_data)

    def test_02_prometheus_metrics(self):
        """2. Testing /metrics Prometheus exposition endpoint."""
        res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/plain", res.headers.get("content-type", ""))
        self.assertIn("primegate_requests_total", res.text)
        self.assertIn("primegate_tokens_total", res.text)

    def test_03_models_endpoint(self):
        """3. Testing /v1/models with authentication."""
        # Unauthenticated request fails with 401
        res_unauth = self.client.get("/v1/models")
        self.assertEqual(res_unauth.status_code, 401)

        # Authenticated request succeeds
        res_auth = self.client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        self.assertEqual(res_auth.status_code, 200)
        data = res_auth.json()
        self.assertTrue(len(data.get("data", [])) > 0)
        model_ids = [m["id"] for m in data["data"]]
        self.assertTrue(any("gemini" in m for m in model_ids))
        self.assertTrue(any("claude" in m for m in model_ids))

    def test_04_openai_chat_completions(self):
        """4. Testing OpenAI /v1/chat/completions translation and response structure."""
        from contextlib import asynccontextmanager

        chunk = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Paris is the capital of France."}],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 8,
                "totalTokenCount": 23
            }
        }

        async def mock_aiter():
            yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        mock_http_res = MagicMock()
        mock_http_res.status_code = 200
        mock_http_res.aiter_lines = mock_aiter
        mock_http_res.aread = AsyncMock(return_value=b"")

        @asynccontextmanager
        async def mock_stream(*args, **kwargs):
            yield mock_http_res

        mock_client = MagicMock()
        mock_client.stream = mock_stream
        mock_client.build_request = MagicMock(return_value="req")
        mock_client.send = AsyncMock(return_value=mock_http_res)

        with patch("prime_gate.server.get_access_token", return_value="mock_access_token"):
            with patch("prime_gate.server.get_shared_client", return_value=mock_client):
                payload = {
                    "model": "gemini-3.8-flash",
                    "messages": [{"role": "user", "content": "What is the capital of France?"}],
                    "stream": False
                }
                res = self.client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload
                )
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["object"], "chat.completion")
                self.assertIn("Paris", data["choices"][0]["message"]["content"])
                self.assertEqual(data["choices"][0]["finish_reason"], "stop")
                self.assertIn("x-request-id", res.headers)

    def test_05_openai_tool_calling(self):
        """5. Testing OpenAI function / tool calling translation."""
        from prime_gate.translator import transform_openai_to_antigravity
        body = {
            "model": "gemini-3.8-flash",
            "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                            "required": ["location"]
                        }
                    }
                }
            ]
        }
        resolved_model, payload = transform_openai_to_antigravity(body)
        self.assertIn("tools", payload)
        self.assertTrue(len(payload["tools"][0]["functionDeclarations"]) > 0)
        self.assertEqual(payload["tools"][0]["functionDeclarations"][0]["name"], "get_weather")

    def test_06_anthropic_messages_non_stream_and_count_tokens(self):
        """6. Testing Native Anthropic /v1/messages and /v1/messages/count_tokens."""
        # A. count_tokens
        count_res = self.client.post(
            "/v1/messages/count_tokens",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-3-7-sonnet",
                "messages": [{"role": "user", "content": "Count these tokens please."}]
            }
        )
        self.assertEqual(count_res.status_code, 200)
        self.assertIn("input_tokens", count_res.json())
        self.assertTrue(count_res.json()["input_tokens"] > 0)

        # B. Non-streaming messages
        chunk = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Hello from Claude translation!"}],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 20,
                "candidatesTokenCount": 10,
                "totalTokenCount": 30
            }
        }

        async def mock_aiter():
            yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        mock_http_res = MagicMock()
        mock_http_res.status_code = 200
        mock_http_res.aiter_lines = mock_aiter
        mock_http_res.aread = AsyncMock(return_value=b"")

        mock_client = MagicMock()
        mock_client.build_request = MagicMock(return_value="req")
        mock_client.send = AsyncMock(return_value=mock_http_res)

        with patch("prime_gate.server.get_access_token", return_value="mock_access_token"):
            with patch("prime_gate.server.get_shared_client", return_value=mock_client):
                msg_res = self.client.post(
                    "/v1/messages",
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                    json={
                        "model": "claude-3-7-sonnet",
                        "messages": [{"role": "user", "content": "Hello Claude"}],
                        "stream": False
                    }
                )
                self.assertEqual(msg_res.status_code, 200)
                data = msg_res.json()
                self.assertEqual(data["type"], "message")
                self.assertEqual(data["role"], "assistant")
                self.assertEqual(data["content"][0]["type"], "text")
                self.assertIn("Claude", data["content"][0]["text"])

    def test_07_agent_loop_guard(self):
        """7. Testing Sentinel Agent Loop Killer."""
        # Simulate an agent making repeated identical tool calls
        messages = [
            {"role": "user", "content": "Fix the bug"},
            {"role": "assistant", "tool_calls": [{"id": "1", "function": {"name": "read_file", "arguments": '{"path":"app.py"}'}}]},
            {"role": "tool", "content": "File not found"},
            {"role": "assistant", "tool_calls": [{"id": "2", "function": {"name": "read_file", "arguments": '{"path":"app.py"}'}}]},
            {"role": "tool", "content": "File not found"},
            {"role": "assistant", "tool_calls": [{"id": "3", "function": {"name": "read_file", "arguments": '{"path":"app.py"}'}}]},
            {"role": "tool", "content": "File not found"},
        ]
        intervened, loop_detected, loop_sig = AgentLoopGuard.check_and_intervene(messages, max_repeats=3)
        self.assertTrue(loop_detected)
        self.assertEqual(loop_sig, "read_file")
        # Check that intervention message was appended
        self.assertEqual(intervened[-1]["role"], "user")
        self.assertIn("[SYSTEM SAFETY INTERVENTION]", intervened[-1]["content"])

    def test_08_search_endpoint(self):
        """8. Testing Web Search endpoint (/v1/search & /search)."""
        mock_results = [{"title": "Prime Gate", "url": "https://example.com", "snippet": "AI Gateway"}]
        with patch("prime_gate.server.search_web", return_value=mock_results):
            res = self.client.post(
                "/v1/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"query": "prime gate proxy", "max_results": 3}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("results", data)
            self.assertEqual(len(data["results"]), 1)
            self.assertEqual(data["results"][0]["title"], "Prime Gate")

if __name__ == "__main__":
    unittest.main()
