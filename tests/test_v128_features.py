import unittest
import json
from prime_gate.translator.response_converter import format_sse_chunk, format_non_stream_response
from prime_gate.translator.anthropic_converter import transform_anthropic_to_antigravity


class TestV128Features(unittest.TestCase):
    def test_initial_sse_chunk_has_no_empty_content_string(self):
        """Standard OpenAI streaming initial chunk contains only role: assistant."""
        chunk_str = format_sse_chunk("chatcmpl-test", 1729900000, "gemini-3.8-flash-high", {"role": "assistant"})
        self.assertTrue(chunk_str.startswith("data: "))
        self.assertTrue(chunk_str.endswith("\n\n"))
        payload = json.loads(chunk_str[6:].strip())
        delta = payload["choices"][0]["delta"]
        self.assertEqual(delta.get("role"), "assistant")
        self.assertNotIn("content", delta)

    def test_non_stream_response_has_null_content_on_tool_calls(self):
        """Tool call response must return content: None (JSON null) if no text was generated."""
        tool_calls = [{
            "id": "call_123",
            "type": "function",
            "function": {"name": "bash", "arguments": "{\"command\":\"ls\"}"}
        }]
        res = format_non_stream_response(
            completion_id="chatcmpl-123",
            created=1729900000,
            model="gemini-3.8-flash-high",
            content_text="",
            tool_calls=tool_calls
        )
        msg = res["choices"][0]["message"]
        self.assertIsNone(msg["content"])
        self.assertEqual(msg["tool_calls"], tool_calls)
        self.assertEqual(res["choices"][0]["finish_reason"], "tool_calls")

    def test_anthropic_protocol_conversion_handles_tool_use_and_tool_result(self):
        """Native Anthropic protocol maps tool_result in user role without lowerToolMessages issues."""
        body = {
            "model": "gemini-3.8-flash-high",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": "Run echo NEXT_TRY"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_abc123",
                            "name": "bash",
                            "input": {"command": "echo NEXT_TRY"}
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_abc123",
                            "content": "NEXT_TRY\n"
                        }
                    ]
                }
            ]
        }
        model, payload = transform_anthropic_to_antigravity(body)
        self.assertIn("contents", payload)
        user_turns = [c for c in payload["contents"] if c["role"] == "user"]
        self.assertTrue(len(user_turns) >= 2)
        fn_part = user_turns[-1]["parts"][0]
        self.assertIn("functionResponse", fn_part)
        self.assertEqual(fn_part["functionResponse"]["id"], "toolu_abc123")
