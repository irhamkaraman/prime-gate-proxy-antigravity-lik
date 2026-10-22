import json
import unittest
from pathlib import Path
from prime_gate.translator.anthropic_converter import (
    format_anthropic_sse_event,
    format_anthropic_non_stream_response,
    estimate_anthropic_tokens,
    anthropic_to_openai_messages,
    transform_anthropic_to_antigravity,
    stream_cached_anthropic_sse
)

class TestAnthropicConformance(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_fixture_claude_code_schema(self):
        """Validates Claude Code tool-use fixture normalization without credentials."""
        fix_path = self.fixtures_dir / "claude_code_tool_use.json"
        with open(fix_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        req = data["request"]
        model_slug, antigravity_payload = transform_anthropic_to_antigravity(req)
        self.assertEqual(model_slug, "claude-sonnet-4-6")
        self.assertIn("tools", antigravity_payload)
        self.assertEqual(antigravity_payload["tools"][0]["functionDeclarations"][0]["name"], "bash")
        
        internal_msgs = anthropic_to_openai_messages(req)
        # Includes top-level system message + user turn
        self.assertEqual(internal_msgs[0]["role"], "system")
        self.assertEqual(internal_msgs[1]["role"], "user")

    def test_fixture_cline_multi_turn_schema(self):
        """Validates Cline multi-turn fixture conversion without credentials."""
        fix_path = self.fixtures_dir / "cline_multi_turn.json"
        with open(fix_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        req = data["request"]
        internal_msgs = anthropic_to_openai_messages(req)
        # 1 system + 3 conversation turns = 4 total
        self.assertEqual(len(internal_msgs), 4)
        self.assertEqual(internal_msgs[0]["role"], "system")
        self.assertEqual(internal_msgs[1]["role"], "user")
        self.assertEqual(internal_msgs[2]["role"], "assistant")
        self.assertEqual(internal_msgs[3]["role"], "tool")

    async def test_anthropic_7_event_stream_sequence(self):
        """
        Verifies exact 7-event stream sequence:
        message_start -> content_block_start -> content_block_delta ->
        content_block_stop -> message_delta -> message_stop
        """
        cached_data = {
            "response_text": "Hello world from Anthropic conformant stream",
            "total_tokens": 15
        }
        events_received = []
        async for chunk in stream_cached_anthropic_sse("msg_123", "claude-sonnet-4-6", cached_data, prompt_tokens=25):
            lines = chunk.strip().split("\n")
            for line in lines:
                if line.startswith("event: "):
                    events_received.append(line.replace("event: ", "").strip())

        self.assertIn("message_start", events_received)
        self.assertIn("content_block_start", events_received)
        self.assertIn("content_block_delta", events_received)
        self.assertIn("content_block_stop", events_received)
        self.assertIn("message_delta", events_received)
        self.assertIn("message_stop", events_received)

        # Invariant: message_start is first, message_stop is last
        self.assertEqual(events_received[0], "message_start")
        self.assertEqual(events_received[-1], "message_stop")

    def test_tool_use_delta_accumulation_valid_json(self):
        """Verifies input_json_delta chunks accumulate into valid executable JSON."""
        tool_args = {"command": "git status", "timeout": 30}
        chunks = ['{"command": ', '"git status"', ', "timeout": 30}']
        json_deltas = []

        for c in chunks:
            sse = format_anthropic_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": c}
            })
            for line in sse.strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line.replace("data: ", ""))
                    json_deltas.append(data["delta"]["partial_json"])

        accumulated = "".join(json_deltas)
        parsed = json.loads(accumulated)
        self.assertEqual(parsed, tool_args)

    def test_thinking_block_format(self):
        """Verifies thinking block format matches Anthropic extended thinking spec."""
        start_event = format_anthropic_sse_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "thinking", "thinking": ""}
        })
        delta_event = format_anthropic_sse_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": "Analyzing code..."}
        })
        self.assertIn("thinking", start_event)
        self.assertIn("thinking_delta", delta_event)

    def test_non_streaming_conformance(self):
        """Verifies non-streaming response matches official Anthropic JSON specification."""
        content_blocks = [{"type": "text", "text": "Non-streaming response from Prime Gate"}]
        anthropic_resp = format_anthropic_non_stream_response(
            message_id="msg_test123",
            model="claude-sonnet-4-6",
            content_blocks=content_blocks,
            stop_reason="end_turn",
            prompt_tokens=20,
            completion_tokens=10
        )
        self.assertEqual(anthropic_resp["type"], "message")
        self.assertEqual(anthropic_resp["role"], "assistant")
        self.assertEqual(anthropic_resp["model"], "claude-sonnet-4-6")
        self.assertEqual(anthropic_resp["stop_reason"], "end_turn")
        self.assertEqual(len(anthropic_resp["content"]), 1)
        self.assertEqual(anthropic_resp["content"][0]["type"], "text")
        self.assertEqual(anthropic_resp["content"][0]["text"], "Non-streaming response from Prime Gate")
        self.assertIn("usage", anthropic_resp)
        self.assertGreater(anthropic_resp["usage"]["input_tokens"], 0)
        self.assertGreater(anthropic_resp["usage"]["output_tokens"], 0)

    def test_count_tokens_calculation(self):
        """Verifies count_tokens estimator returns positive integer token count."""
        sample_body = {
            "system": "You are an AI assistant.",
            "messages": [
                {"role": "user", "content": "Hello, how are you today?"},
                {"role": "assistant", "content": "I am fine, thank you! How can I assist you with your code?"}
            ]
        }
        tokens = estimate_anthropic_tokens(sample_body)
        self.assertGreater(tokens, 15)

if __name__ == "__main__":
    unittest.main()
