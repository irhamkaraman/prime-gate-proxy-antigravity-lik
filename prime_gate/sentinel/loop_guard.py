import json
import hashlib
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("prime_gate.sentinel.loop_guard")

class AgentLoopGuard:
    """
    Detects and breaks autonomous AI agent runaway execution loops.
    
    Identifies patterns where an agent repeatedly executes the same failing tool
    with identical parameters, injecting surgical system interventions to prevent
    infinite execution loops and massive quota drain.
    """

    MAX_CONSECUTIVE_IDENTICAL_CALLS = 3

    @staticmethod
    def _compute_tool_signature(tool_call: Dict[str, Any]) -> str:
        """Computes a deterministic hash for a tool call based on name and arguments."""
        fn = tool_call.get("function", {})
        name = fn.get("name", "")
        raw_args = fn.get("arguments", "{}")
        
        # Normalize arguments
        try:
            if isinstance(raw_args, str):
                parsed = json.loads(raw_args)
            elif isinstance(raw_args, dict):
                parsed = raw_args
            else:
                parsed = {}
            norm_args = json.dumps(parsed, sort_keys=True, separators=(',', ':'))
        except Exception:
            norm_args = str(raw_args)

        h = hashlib.sha256(f"{name}:{norm_args}".encode("utf-8")).hexdigest()
        return f"{name}:{h[:16]}"

    @classmethod
    def check_and_intervene(
        cls,
        messages: List[Dict[str, Any]],
        max_repeats: int = 3
    ) -> Tuple[List[Dict[str, Any]], bool, Optional[str]]:
        """
        Inspects message history for repetitive failing tool loops.
        
        If >= max_repeats identical tool calls are detected in the trailing turns,
        injects a corrective system message at the end of the history to force
        the model to change strategy.
        
        Returns:
            (messages_list, has_intervened, detected_tool_name)
        """
        if not messages or len(messages) < 4:
            return messages, False, None

        # Extract all tool calls in chronological order from assistant messages
        recent_signatures: List[Tuple[str, str]] = [] # (tool_name, signature)
        
        for msg in messages:
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                for tc in msg.get("tool_calls", []):
                    sig = cls._compute_tool_signature(tc)
                    fn_name = tc.get("function", {}).get("name", "tool")
                    recent_signatures.append((fn_name, sig))

        if len(recent_signatures) < max_repeats:
            return messages, False, None

        # Check if the last N tool calls have identical signatures
        last_sig = recent_signatures[-1][1]
        last_name = recent_signatures[-1][0]
        consecutive_matches = 0

        for name, sig in reversed(recent_signatures):
            if sig == last_sig:
                consecutive_matches += 1
            else:
                break

        if consecutive_matches >= max_repeats:
            logger.warning(
                f"[LOOP GUARD] Detected runaway loop: Tool '{last_name}' called "
                f"{consecutive_matches} times consecutively with identical arguments!"
            )
            
            intervention_text = (
                f"[SYSTEM SAFETY INTERVENTION]: You have invoked tool '{last_name}' with the exact same "
                f"parameters {consecutive_matches} times consecutively without making forward progress. "
                f"DO NOT repeat this tool call. Analyze why previous attempts failed, re-evaluate your approach, "
                f"and either choose a different action or explain the issue clearly."
            )
            
            # Check if intervention was already injected to avoid duplicating it
            if messages and messages[-1].get("content") == intervention_text:
                return messages, False, None

            new_messages = list(messages)
            new_messages.append({
                "role": "user",
                "content": intervention_text
            })
            return new_messages, True, last_name

        return messages, False, None
