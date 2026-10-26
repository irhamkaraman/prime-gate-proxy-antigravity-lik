import unittest
from prime_gate.translator.request_converter import transform_openai_to_antigravity
from prime_gate.compactor import ContextCompactor
from prime_gate.daemon.process_posix import _is_pid_alive
from prime_gate.server import _check_github_sync


class TestV127Features(unittest.TestCase):
    def test_request_converter_hyphenated_tool_result_in_tool_role(self):
        """OpenCode / Vercel AI SDK sends tool-result parts in role: 'tool'."""
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "user", "content": "Check project status"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": "{\"path\": \"package.json\"}"}
                        }
                    ]
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_abc123",
                    "content": [
                        {
                            "type": "tool-result",
                            "toolCallId": "call_abc123",
                            "result": "{\"name\": \"my-project\", \"version\": \"1.0.0\"}"
                        }
                    ]
                }
            ]
        }
        model, payload = transform_openai_to_antigravity(body)
        self.assertIn("contents", payload)
        # Find the functionResponse turn
        user_turns = [c for c in payload["contents"] if c["role"] == "user"]
        self.assertTrue(len(user_turns) >= 2)
        fn_part = user_turns[-1]["parts"][0]
        self.assertIn("functionResponse", fn_part)
        self.assertEqual(fn_part["functionResponse"]["id"], "call_abc123")
        # Response must be a dict (google.protobuf.Struct), never a raw list
        self.assertIsInstance(fn_part["functionResponse"]["response"], dict)

    def test_request_converter_hyphenated_tool_result_in_user_role(self):
        """Vercel AI SDK / Anthropic sends tool-result parts inside role: 'user'."""
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "user", "content": "List files"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_xyz789",
                            "type": "function",
                            "function": {"name": "ls", "arguments": "{}"}
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool-result",
                            "tool_use_id": "call_xyz789",
                            "result": "file1.txt\nfile2.txt"
                        }
                    ]
                }
            ]
        }
        model, payload = transform_openai_to_antigravity(body)
        user_turns = [c for c in payload["contents"] if c["role"] == "user"]
        has_fn_resp = any("functionResponse" in p for t in user_turns for p in t["parts"])
        self.assertTrue(has_fn_resp)

    def test_compactor_recognizes_hyphenated_tool_result(self):
        """Compactor correctly identifies and compacts tool-result parts without changing block type."""
        msg = {
            "role": "user",
            "content": [
                {
                    "type": "tool-result",
                    "tool_use_id": "call_1",
                    "result": ("line output...\n" * 50)
                }
            ]
        }
        self.assertTrue(ContextCompactor._is_tool_message(msg))

        # Compact message
        compacted, stats = ContextCompactor.compact_messages(
            [
                {"role": "user", "content": "start"},
                {"role": "assistant", "content": "executing", "tool_calls": [{"id": "call_1", "function": {"name": "run"}}]},
                msg,
                {"role": "user", "content": "step 2"},
                {"role": "assistant", "content": "next", "tool_calls": [{"id": "call_2", "function": {"name": "run"}}]},
                {"role": "tool", "tool_call_id": "call_2", "content": "ok"},
                {"role": "user", "content": "step 3"},
                {"role": "assistant", "content": "next 3"},
                {"role": "user", "content": "step 4"},
            ],
            config={"window_turns": 2, "window_tools": 1, "max_tool_chars": 100}
        )
        # Type must remain 'tool-result', NOT mutated into 'text'
        self.assertEqual(compacted[2]["content"][0]["type"], "tool-result")

    def test_posix_daemon_liveness_check(self):
        """POSIX daemon liveness check safely handles invalid and negative PIDs."""
        self.assertFalse(_is_pid_alive(None))
        self.assertFalse(_is_pid_alive(-1))
        self.assertFalse(_is_pid_alive(0))
        self.assertFalse(_is_pid_alive(99999999))

    def test_check_github_sync_npm_first(self):
        """Check sync prioritizes npm and correctly identifies synced state."""
        sync_info = _check_github_sync(force_refresh=True)
        self.assertIn("current_version", sync_info)
        self.assertIn("update_available", sync_info)
        self.assertIn("is_synced", sync_info)
        self.assertIn("install_command", sync_info)
        self.assertIn("npx_command", sync_info)
        # If current version is equal or newer than published npm (1.2.6), update_available must be False
        if sync_info.get("npm_version") == "1.2.6":
            self.assertFalse(sync_info["update_available"])
            self.assertTrue(sync_info["is_synced"])


if __name__ == "__main__":
    unittest.main()
