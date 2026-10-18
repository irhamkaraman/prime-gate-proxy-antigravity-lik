import copy
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("prime_gate.compactor")

class ContextCompactor:
    """
    Intelligent conversation context compactor for AI coding agents.
    
    Compresses excessive historical tool execution outputs (such as massive read_file,
    terminal command logs, and file listings) older than `window_turns` to prevent
    30k - 100k+ token blowups while preserving the latest active turns and system instructions.
    """

    DEFAULT_CONFIG = {
        "enabled": True,
        "window_turns": 3,
        "max_tool_chars": 600,
        "preserve_head_lines": 6,
        "preserve_tail_lines": 6,
    }

    @classmethod
    def compact_messages(
        cls,
        messages: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Compacts the message history.
        
        Args:
            messages: OpenAI-format list of message dicts.
            config: Optional override dictionary for compactor parameters.
            
        Returns:
            Tuple of (compacted_messages, estimated_tokens_pruned).
        """
        cfg = dict(cls.DEFAULT_CONFIG)
        if config:
            cfg.update(config)

        if not cfg.get("enabled", True) or not messages:
            return messages, 0

        window_turns = int(cfg.get("window_turns", 3))
        max_tool_chars = int(cfg.get("max_tool_chars", 600))
        head_lines = int(cfg.get("preserve_head_lines", 6))
        tail_lines = int(cfg.get("preserve_tail_lines", 6))

        total_pruned_chars = 0
        compacted: List[Dict[str, Any]] = []

        # Step 1: Identify turns backwards (a user message typically marks a new user turn)
        # Find index of user messages to establish the active window cutoff
        user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
        
        # If there are more user turns than the active window, cutoff is the Nth latest user message
        cutoff_index = 0
        if len(user_indices) > window_turns:
            cutoff_index = user_indices[-window_turns]

        for idx, msg in enumerate(messages):
            msg_copy = copy.deepcopy(msg)
            role = msg_copy.get("role", "")
            
            # System prompt and messages within the active window are preserved 100%
            if role == "system" or idx >= cutoff_index:
                compacted.append(msg_copy)
                continue

            # Process historical tool messages or tool call results
            if role == "tool" or "tool_call_id" in msg_copy:
                content = msg_copy.get("content", "")
                if isinstance(content, str) and len(content) > max_tool_chars:
                    lines = content.splitlines()
                    if len(lines) > (head_lines + tail_lines + 2):
                        kept_head = lines[:head_lines]
                        kept_tail = lines[-tail_lines:]
                        orig_len = len(content)
                        orig_lines = len(lines)
                        
                        pruned_marker = (
                            f"\n[... Historical tool execution output pruned by Prime Gate Compactor "
                            f"(Original: {orig_len:,} chars, {orig_lines} lines) ...]\n"
                        )
                        new_content = "\n".join(kept_head) + pruned_marker + "\n".join(kept_tail)
                        
                        pruned_diff = len(content) - len(new_content)
                        if pruned_diff > 0:
                            total_pruned_chars += pruned_diff
                            msg_copy["content"] = new_content
                elif isinstance(content, list):
                    # Handle multimodal or structured text parts
                    new_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            p_text = part.get("text", "")
                            if len(p_text) > max_tool_chars:
                                p_lines = p_text.splitlines()
                                if len(p_lines) > (head_lines + tail_lines + 2):
                                    kept_head = p_lines[:head_lines]
                                    kept_tail = p_lines[-tail_lines:]
                                    pruned_marker = (
                                        f"\n[... Historical tool output pruned by Prime Gate Compactor "
                                        f"({len(p_text):,} chars) ...]\n"
                                    )
                                    part["text"] = "\n".join(kept_head) + pruned_marker + "\n".join(kept_tail)
                                    total_pruned_chars += (len(p_text) - len(part["text"]))
                        new_parts.append(part)
                    msg_copy["content"] = new_parts

            compacted.append(msg_copy)

        estimated_tokens_pruned = max(0, total_pruned_chars // 4)
        if estimated_tokens_pruned > 0:
            logger.info(
                f"[COMPACTOR] Pruned ~{estimated_tokens_pruned:,} tokens ({total_pruned_chars:,} chars) "
                f"from historical turns beyond last {window_turns} active turns."
            )

        return compacted, estimated_tokens_pruned
