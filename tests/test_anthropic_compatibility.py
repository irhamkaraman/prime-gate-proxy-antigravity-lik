import unittest
from prime_gate.translator.anthropic_converter import (
    transform_anthropic_to_antigravity,
    anthropic_to_openai_messages,
    format_anthropic_non_stream_response,
    format_anthropic_sse_event,
    estimate_anthropic_tokens
)

class TestAnthropicCompatibility(unittest.TestCase):

    def test_transform_anthropic_simple_text(self):
        body = {
            "model": "claude-3-5-sonnet-20241022",
            "system": "You are a helpful coding assistant.",
            "messages": [
                {"role": "user", "content": "Hello Claude!"}
            ],
            "max_tokens": 1024,
            "temperature": 0.5
        }
        model, req_payload = transform_anthropic_to_antigravity(body)
        self.assertTrue("claude" in model.lower() or "flash" in model.lower() or "gemini" in model.lower())
        
        # Verify systemInstruction
        sys_inst = req_payload.get("systemInstruction", {})
        self.assertEqual(sys_inst.get("role"), "user")
        self.assertTrue(sys_inst["parts"][0]["text"].startswith("You are a helpful coding assistant."))

        # Verify contents
        contents = req_payload.get("contents", [])
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[0]["parts"][0]["text"], "Hello Claude!")

        # Verify generationConfig
        gen_cfg = req_payload.get("generationConfig", {})
        self.assertEqual(gen_cfg.get("maxOutputTokens"), 1024)
        self.assertEqual(gen_cfg.get("temperature"), 0.5)

    def test_transform_anthropic_multimodal_image(self):
        body = {
            "model": "claude-3-5-sonnet",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "dGVzdGltYWdlZGF0YQ=="
                            }
                        }
                    ]
                }
            ]
        }
        _, req_payload = transform_anthropic_to_antigravity(body)
        contents = req_payload.get("contents", [])
        self.assertEqual(len(contents), 1)
        parts = contents[0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["text"], "What is in this image?")
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/jpeg")
        self.assertEqual(parts[1]["inlineData"]["data"], "dGVzdGltYWdlZGF0YQ==")

    def test_transform_anthropic_tools_and_results(self):
        body = {
            "model": "claude-3-5-sonnet-20241022",
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Fetch current weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                        "required": ["location"]
                    }
                }
            ],
            "messages": [
                {"role": "user", "content": "What is the weather in Jakarta?"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_019238491",
                            "name": "get_weather",
                            "input": {"location": "Jakarta"}
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_019238491",
                            "content": '{"temp": 32, "condition": "Sunny"}'
                        }
                    ]
                }
            ]
        }
        _, req_payload = transform_anthropic_to_antigravity(body)
        tools = req_payload.get("tools", [])
        self.assertTrue(len(tools) > 0)
        fn_decl = tools[0]["functionDeclarations"][0]
        self.assertEqual(fn_decl["name"], "get_weather")
        self.assertIn("location", fn_decl["parameters"]["properties"])

        contents = req_payload.get("contents", [])
        self.assertEqual(len(contents), 3)
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[1]["role"], "model")
        self.assertEqual(contents[1]["parts"][0]["functionCall"]["name"], "get_weather")
        self.assertEqual(contents[2]["role"], "user")
        self.assertEqual(contents[2]["parts"][0]["functionResponse"]["name"], "get_weather")

    def test_schema_cleaner_array_and_prefix_items(self):
        from prime_gate.translator.schema_cleaner import clean_schema_for_antigravity
        dirty_schema = {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "prefixItems": [{"type": "string"}]
                    }
                }
            }
        }
        cleaned = clean_schema_for_antigravity(dirty_schema)
        props = cleaned["properties"]["filters"]
        self.assertEqual(props["type"], "array")
        self.assertIn("items", props)
        self.assertNotIn("prefixItems", props["items"])
        self.assertEqual(props["items"]["type"], "array")
        self.assertEqual(props["items"]["items"]["type"], "string")

    def test_anthropic_to_openai_messages_normalization(self):
        body = {
            "system": "System instructions here.",
            "messages": [
                {"role": "user", "content": "Question 1"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Answer 1"},
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "calculator",
                            "input": {"expr": "2+2"}
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_123",
                            "content": "4"
                        }
                    ]
                }
            ]
        }
        norm = anthropic_to_openai_messages(body)
        self.assertEqual(norm[0]["role"], "system")
        self.assertEqual(norm[0]["content"], "System instructions here.")
        self.assertEqual(norm[1]["role"], "user")
        self.assertEqual(norm[1]["content"], "Question 1")
        self.assertEqual(norm[2]["role"], "assistant")
        self.assertTrue("tool_calls" in norm[2])
        self.assertEqual(norm[3]["role"], "tool")
        self.assertEqual(norm[3]["tool_call_id"], "toolu_123")
        self.assertEqual(norm[3]["content"], "4")

    def test_format_anthropic_non_stream_response(self):
        resp = format_anthropic_non_stream_response(
            message_id="msg_test123",
            model="claude-3-5-sonnet",
            content_blocks=[{"type": "text", "text": "Hello Anthropic!"}],
            stop_reason="end_turn",
            prompt_tokens=15,
            completion_tokens=5,
            cache_read_tokens=10
        )
        self.assertEqual(resp["id"], "msg_test123")
        self.assertEqual(resp["type"], "message")
        self.assertEqual(resp["role"], "assistant")
        self.assertEqual(resp["content"][0]["text"], "Hello Anthropic!")
        self.assertEqual(resp["usage"]["input_tokens"], 15)
        self.assertEqual(resp["usage"]["output_tokens"], 5)
        self.assertEqual(resp["usage"]["cache_read_input_tokens"], 10)

    def test_format_anthropic_sse_event(self):
        line = format_anthropic_sse_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hi"}
        })
        self.assertTrue(line.startswith("event: content_block_delta\n"))
        self.assertIn('"delta":{"type":"text_delta","text":"Hi"}', line)
        self.assertTrue(line.endswith("\n\n"))

    def test_estimate_anthropic_tokens(self):
        body = {
            "system": "A" * 40,
            "messages": [
                {"role": "user", "content": "B" * 60}
            ]
        }
        tokens = estimate_anthropic_tokens(body)
        self.assertGreaterEqual(tokens, 20)

if __name__ == "__main__":
    unittest.main()
