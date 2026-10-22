import unittest
import copy
from prime_gate.compactor import ContextCompactor, CompactorStats
from prime_gate.db.engine import BinaryDatabaseEngine

class TestSmartContextCompactor(unittest.TestCase):
    def setUp(self):
        self.large_log = ("INFO: compiling module...\n" * 50) + ("SUCCESS: compiled unit.\n" * 50)
        self.error_log = ("INFO: running test suite...\n" * 20) + (
            "Traceback (most recent call last):\n"
            "  File 'test_runner.py', line 42, in test_main\n"
            "    raise AssertionError('Expected 200 OK, got 500')\n"
            "AssertionError: Expected 200 OK, got 500\n"
            "exit code: 1\n"
        ) + ("FAIL: 1 of 12 tests failed.\n" * 10)

    def test_error_tool_output_never_pruned(self):
        """Invariant #1: Tool outputs containing errors/tracebacks are never pruned."""
        messages = [
            {"role": "system", "content": "You are a coding assistant."},
            {"role": "user", "content": "Run tests."},
            {"role": "assistant", "content": "Running tests...", "tool_calls": [{"id": "call_err", "function": {"name": "bash", "arguments": "{\"cmd\": \"pytest\"}"}}]},
            # Tool with error (old)
            {"role": "tool", "tool_call_id": "call_err", "content": self.error_log},
            # Subsequent turns pushing window
            {"role": "user", "content": "Turn 2"},
            {"role": "assistant", "content": "step 2"},
            {"role": "tool", "tool_call_id": "call_2", "content": "Short output 2"},
            {"role": "user", "content": "Turn 3"},
            {"role": "assistant", "content": "step 3"},
            {"role": "tool", "tool_call_id": "call_3", "content": "Short output 3"},
            {"role": "user", "content": "Turn 4"},
            {"role": "assistant", "content": "step 4"},
            {"role": "tool", "tool_call_id": "call_4", "content": "Short output 4"},
            {"role": "user", "content": "Turn 5"},
        ]
        compacted, stats = ContextCompactor.compact_messages(
            messages,
            config={"window_turns": 2, "window_tools": 1, "preserve_errors": True, "max_tool_chars": 200}
        )
        # Error tool output at index 3 must remain 100% unpruned
        self.assertEqual(compacted[3]["content"], self.error_log)
        self.assertNotIn("output dipangkas", compacted[3]["content"])

    def test_anthropic_is_error_flag_never_pruned(self):
        """Invariant #1 (Anthropic): Blocks with is_error=True are 100% preserved."""
        anthropic_msgs = [
            {"role": "user", "content": "Fix bug"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t_err", "name": "run", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t_err", "content": ("Fatal compiler error\n" * 40), "is_error": True}
            ]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t_ok1", "name": "run", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t_ok1", "content": "Recent ok 1"}
            ]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t_ok2", "name": "run", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t_ok2", "content": "Recent ok 2"}
            ]},
        ]
        compacted = ContextCompactor.compact_anthropic_body_messages(
            anthropic_msgs,
            window_tools=1,
            max_tool_chars=200,
            preserve_errors=True
        )
        err_content = compacted[2]["content"][0]["content"]
        self.assertNotIn("output dipangkas", err_content)
        self.assertIn("Fatal compiler error", err_content)

    def test_re_referenced_tool_output_never_pruned(self):
        """Invariant #2: Tool outputs explicitly referenced downstream are immune to pruning."""
        messages = [
            {"role": "system", "content": "You are a coding assistant."},
            {"role": "user", "content": "Read file foo.py"},
            {"role": "assistant", "content": "Reading...", "tool_calls": [{"id": "call_foo", "function": {"name": "read_file", "arguments": "{\"path\": \"src/foo.py\"}"}}]},
            # Tool call foo (large content)
            {"role": "tool", "tool_call_id": "call_foo", "content": self.large_log},
            # Turn 2
            {"role": "user", "content": "Turn 2"},
            {"role": "tool", "tool_call_id": "c2", "content": "short"},
            # Turn 3
            {"role": "user", "content": "Turn 3"},
            {"role": "tool", "tool_call_id": "c3", "content": "short"},
            # Turn 4: user or assistant explicitly references call_foo or src/foo.py
            {"role": "user", "content": "Regarding src/foo.py that we inspected earlier in call_foo, let's refactor it."},
        ]
        compacted, stats = ContextCompactor.compact_messages(
            messages,
            config={"window_turns": 2, "window_tools": 1, "preserve_re_references": True, "max_tool_chars": 200}
        )
        # Because call_foo and src/foo.py were referenced in downstream turn 4, it should NOT be pruned
        self.assertEqual(compacted[3]["content"], self.large_log)
        self.assertNotIn("output dipangkas", compacted[3]["content"])

    def test_dry_run_payload_unmodified_but_tokens_recorded(self):
        """Invariant #3: dry_run=True returns 100% byte-for-byte original messages."""
        messages = [
            {"role": "system", "content": "You are a developer."},
            {"role": "user", "content": "Step 1"},
            {"role": "assistant", "content": "read", "tool_calls": [{"id": "c1", "function": {"name": "read", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": self.large_log},
            {"role": "user", "content": "Step 2"},
            {"role": "assistant", "content": "read2", "tool_calls": [{"id": "c2", "function": {"name": "read", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c2", "content": "recent short"},
            {"role": "user", "content": "Step 3"},
            {"role": "user", "content": "Step 4"},
        ]
        original_copy = copy.deepcopy(messages)
        compacted, stats = ContextCompactor.compact_messages(
            messages,
            config={"window_turns": 2, "window_tools": 1, "max_tool_chars": 200, "dry_run": True}
        )
        # Payload must be 100% identical to original
        self.assertEqual(compacted, original_copy)
        # But stats must report potential savings and dry_run flag
        self.assertTrue(stats.dry_run)
        self.assertGreater(stats.tokens_saved, 0)
        self.assertGreater(stats.get("chars_saved", 0), 0)
        self.assertEqual(stats.get("pruned_tool_messages"), 1)

    def test_informative_pruned_marker_format(self):
        """Invariant #4: Pruned marker explicitly contains '[output dipangkas: ~N token]'."""
        messages = [
            {"role": "system", "content": "You are a developer."},
            {"role": "user", "content": "Step 1"},
            {"role": "assistant", "content": "read", "tool_calls": [{"id": "c1", "function": {"name": "read", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": self.large_log},
            {"role": "user", "content": "Step 2"},
            {"role": "user", "content": "Step 3"},
            {"role": "user", "content": "Step 4"},
        ]
        compacted, stats = ContextCompactor.compact_messages(
            messages,
            config={"window_turns": 2, "window_tools": 1, "max_tool_chars": 200, "dry_run": False}
        )
        pruned_content = compacted[3]["content"]
        self.assertIn("[output dipangkas: ~", pruned_content)
        self.assertIn("token", pruned_content)
        self.assertIn("Historical tool execution output pruned", pruned_content)

    def test_hierarchical_config_resolution(self):
        """Tests config resolution hierarchy: default < base < client < model."""
        base = {
            "window_turns": 3,
            "max_tool_chars": 600,
            "client_overrides": {
                "cline": {"max_tool_chars": 800, "window_tools": 4},
                "cursor": {"max_tool_chars": 1200}
            },
            "model_overrides": {
                "claude-sonnet-4-6": {"window_turns": 5},
                "gemini-3.8-flash": {"window_turns": 8}
            }
        }
        # 1. Standard fallback
        cfg_default = ContextCompactor.resolve_config("", "", base)
        self.assertEqual(cfg_default["window_turns"], 3)
        self.assertEqual(cfg_default["max_tool_chars"], 600)

        # 2. Client override (cline)
        cfg_cline = ContextCompactor.resolve_config("Cline/3.5.0", "", base)
        self.assertEqual(cfg_cline["max_tool_chars"], 800)
        self.assertEqual(cfg_cline["window_tools"], 4)

        # 3. Model override takes precedence
        cfg_model = ContextCompactor.resolve_config("Cline/3.5.0", "claude-sonnet-4-6", base)
        self.assertEqual(cfg_model["max_tool_chars"], 800)
        self.assertEqual(cfg_model["window_turns"], 5)

    def test_database_compactor_token_recording(self):
        """Verifies database records cumulative tokens saved."""
        db = BinaryDatabaseEngine()
        initial_stats = db.get_compactor_stats()
        initial_tokens = initial_stats.get("compactor_tokens_saved_total", 0)

        db.record_compactor_tokens_saved(250)
        updated_stats = db.get_compactor_stats()
        self.assertEqual(updated_stats["compactor_tokens_saved_total"], initial_tokens + 250)

if __name__ == "__main__":
    unittest.main()
