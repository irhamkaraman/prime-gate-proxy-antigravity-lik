import unittest
from prime_gate.compactor import ContextCompactor

class TestContextCompactor(unittest.TestCase):
    def test_recent_turns_unaffected(self):
        messages = [
            {"role": "system", "content": "You are a senior developer."},
            {"role": "user", "content": "Check my code."},
            {"role": "assistant", "content": "Here is the plan."},
            {"role": "tool", "tool_call_id": "call_1", "content": "Line 1\n" * 100},
            {"role": "user", "content": "Now fix it."}
        ]
        # Active window = 3 user turns, here we only have 2 user turns -> should NOT prune
        compacted, pruned = ContextCompactor.compact_messages(messages, {"window_turns": 3})
        self.assertEqual(pruned, 0)
        self.assertEqual(len(compacted), len(messages))
        self.assertEqual(compacted[3]["content"], messages[3]["content"])

    def test_historical_tool_pruning(self):
        # 4 user turns -> the first tool output in turn 1 should be pruned
        large_tool_output = "\n".join([f"file content row {i}: data data data data data" for i in range(100)])
        messages = [
            {"role": "system", "content": "You are an AI assistant."},
            # Turn 1 (Old)
            {"role": "user", "content": "Read file A"},
            {"role": "tool", "tool_call_id": "call_old", "content": large_tool_output},
            # Turn 2
            {"role": "user", "content": "Read file B"},
            {"role": "tool", "tool_call_id": "call_b", "content": "Short output"},
            # Turn 3
            {"role": "user", "content": "Read file C"},
            {"role": "tool", "tool_call_id": "call_c", "content": "Short output"},
            # Turn 4 (Latest active)
            {"role": "user", "content": "Final analysis"}
        ]
        compacted, pruned = ContextCompactor.compact_messages(messages, {"window_turns": 3, "max_tool_chars": 200})
        self.assertGreater(pruned, 0)
        self.assertIn("Historical tool execution output pruned", compacted[2]["content"])
        # Ensure system prompt and latest user prompt are unaffected
    def test_server_style_compactor_call(self):
        large_output = ("data row verbose output " * 10 + "\n") * 50
        messages = [
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "ok"},
            {"role": "tool", "tool_call_id": "c1", "content": large_output},
            {"role": "user", "content": "2"},
            {"role": "user", "content": "3"},
            {"role": "user", "content": "4"},
            {"role": "user", "content": "5"},
        ]
        compacted, stats = ContextCompactor.compact_messages(
            messages=messages,
            keep_recent_user_turns=3,
            max_tool_output_lines=20
        )
        self.assertTrue(stats.get("compacted"))
        self.assertGreater(stats["pruned_tool_messages"], 0)
        self.assertGreater(stats["chars_saved"], 0)
        self.assertGreater(int(stats), 0)

if __name__ == "__main__":
    unittest.main()

