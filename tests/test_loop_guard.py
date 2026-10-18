import unittest
from prime_gate.sentinel.loop_guard import AgentLoopGuard

class TestAgentLoopGuard(unittest.TestCase):
    def test_no_loop_normal_chat(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        res_msgs, intervened, tool = AgentLoopGuard.check_and_intervene(messages)
        self.assertFalse(intervened)
        self.assertIsNone(tool)
        self.assertEqual(len(res_msgs), 2)

    def test_detect_identical_tool_loop(self):
        tool_call_payload = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": '{"path": "package.json"}'
            }
        }
        # Simulate 3 consecutive identical tool calls
        messages = [
            {"role": "user", "content": "Fix dependencies"},
            {"role": "assistant", "tool_calls": [tool_call_payload]},
            {"role": "tool", "tool_call_id": "call_1", "content": "error reading file"},
            {"role": "assistant", "tool_calls": [tool_call_payload]},
            {"role": "tool", "tool_call_id": "call_1", "content": "error reading file"},
            {"role": "assistant", "tool_calls": [tool_call_payload]},
            {"role": "tool", "tool_call_id": "call_1", "content": "error reading file"}
        ]
        res_msgs, intervened, tool = AgentLoopGuard.check_and_intervene(messages, max_repeats=3)
        self.assertTrue(intervened)
        self.assertEqual(tool, "read_file")
        self.assertIn("[SYSTEM SAFETY INTERVENTION]", res_msgs[-1]["content"])

if __name__ == "__main__":
    unittest.main()
