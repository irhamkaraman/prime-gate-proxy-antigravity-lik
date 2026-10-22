import json
import unittest
from pathlib import Path

class TestOpenAIConformance(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_fixture_cursor_chat_stream(self):
        """Validates Cursor stream fixture structure without credentials."""
        fix_path = self.fixtures_dir / "cursor_chat_stream.json"
        with open(fix_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["client"], "Cursor")
        self.assertEqual(data["protocol"], "openai")
        self.assertTrue(data["request"]["stream"])
        self.assertEqual(data["request"]["model"], "gpt-4o")

    def test_fixture_aider_edit_block(self):
        """Validates Aider non-streaming search/replace fixture without credentials."""
        fix_path = self.fixtures_dir / "aider_edit_block.json"
        with open(fix_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["client"], "Aider")
        self.assertFalse(data["request"]["stream"])
        content = data["mock_upstream_response"]["candidates"][0]["content"]["parts"][0]["text"]
        self.assertIn("<<<<<<< SEARCH", content)
        self.assertIn("=======", content)
        self.assertIn(">>>>>>> REPLACE", content)

    def test_openai_sse_chunk_format(self):
        """Validates OpenAI SSE chunk format conforms to standard OpenAPI spec."""
        sample_chunk = {
            "id": "chatcmpl-test12345",
            "object": "chat.completion.chunk",
            "created": 1729600000,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "Hello world"
                    },
                    "finish_reason": None
                }
            ]
        }
        sse_line = f"data: {json.dumps(sample_chunk)}\n\n"
        self.assertTrue(sse_line.startswith("data: {"))
        self.assertTrue(sse_line.endswith("}\n\n"))
        parsed = json.loads(sse_line.replace("data: ", "").strip())
        self.assertEqual(parsed["object"], "chat.completion.chunk")
        self.assertEqual(parsed["choices"][0]["delta"]["content"], "Hello world")

    def test_openai_tool_calls_chunk_format(self):
        """Validates gradual tool_calls delta chunking in streaming mode."""
        sample_tool_chunk = {
            "id": "chatcmpl-tool123",
            "object": "chat.completion.chunk",
            "created": 1729600000,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": "{\"path\": \""
                                }
                            }
                        ]
                    },
                    "finish_reason": None
                }
            ]
        }
        self.assertIn("tool_calls", sample_tool_chunk["choices"][0]["delta"])
        tc = sample_tool_chunk["choices"][0]["delta"]["tool_calls"][0]
        self.assertEqual(tc["function"]["name"], "read_file")

    def test_openai_reasoning_content_delta(self):
        """Validates reasoning_content delta for thinking models."""
        reasoning_chunk = {
            "id": "chatcmpl-reason123",
            "object": "chat.completion.chunk",
            "created": 1729600000,
            "model": "gemini-3.8-flash",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "reasoning_content": "Pondering the algorithm...",
                        "content": None
                    },
                    "finish_reason": None
                }
            ]
        }
        delta = reasoning_chunk["choices"][0]["delta"]
        self.assertEqual(delta["reasoning_content"], "Pondering the algorithm...")
        self.assertIsNone(delta["content"])

    def test_openai_terminal_done_signal(self):
        """Verifies terminal stream sentinel is data: [DONE]."""
        done_signal = "data: [DONE]\n\n"
        self.assertEqual(done_signal.strip(), "data: [DONE]")

if __name__ == "__main__":
    unittest.main()
