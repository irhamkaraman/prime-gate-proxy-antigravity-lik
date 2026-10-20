import copy
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("prime_gate.compactor")

class CompactorStats(dict):
    """
    Statistics dictionary that also behaves as an integer (tokens_saved)
    for seamless backwards compatibility.
    """
    def __init__(self, tokens_saved: int = 0, chars_saved: int = 0, pruned_tool_messages: int = 0):
        super().__init__({
            "compacted": tokens_saved > 0 or chars_saved > 0,
            "tokens_saved": tokens_saved,
            "chars_saved": chars_saved,
            "pruned_tool_messages": pruned_tool_messages,
        })
        self.tokens_saved = tokens_saved

    def __int__(self):
        return self.tokens_saved

    def __eq__(self, other):
        if isinstance(other, int):
            return self.tokens_saved == other
        return super().__eq__(other)

    def __gt__(self, other):
        if isinstance(other, int):
            return self.tokens_saved > other
        return super().__gt__(other)

    def __ge__(self, other):
        if isinstance(other, int):
            return self.tokens_saved >= other
        return super().__ge__(other)

    def __lt__(self, other):
        if isinstance(other, int):
            return self.tokens_saved < other
        return super().__lt__(other)

    def __le__(self, other):
        if isinstance(other, int):
            return self.tokens_saved <= other
        return super().__le__(other)


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
        config: Optional[Dict[str, Any]] = None,
        keep_recent_user_turns: Optional[int] = None,
        max_tool_output_lines: Optional[int] = None,
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], CompactorStats]:
        """
        Compacts the message history.
        
        Args:
            messages: OpenAI-format list of message dicts.
            config: Optional override dictionary for compactor parameters.
            keep_recent_user_turns: Optional override for active user turns window.
            max_tool_output_lines: Optional override for maximum tool output lines preserved.
            
        Returns:
            Tuple of (compacted_messages, compactor_stats).
        """
        cfg = dict(cls.DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        if keep_recent_user_turns is not None:
            cfg["window_turns"] = keep_recent_user_turns
        if max_tool_output_lines is not None:
            half = max(2, max_tool_output_lines // 2)
            cfg["preserve_head_lines"] = half
            cfg["preserve_tail_lines"] = half
        for k, v in kwargs.items():
            cfg[k] = v

        if not cfg.get("enabled", True) or not messages:
            return messages, CompactorStats()

        window_turns = int(cfg.get("window_turns", 3))
        max_tool_chars = int(cfg.get("max_tool_chars", 600))
        head_lines = int(cfg.get("preserve_head_lines", 6))
        tail_lines = int(cfg.get("preserve_tail_lines", 6))

        total_pruned_chars = 0
        pruned_tool_count = 0
        compacted: List[Dict[str, Any]] = []

        # Step 1: Identify turns backwards (a user message typically marks a new user turn)
        # Find index of user messages to establish the active window cutoff
        user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
        
        # If there are more user turns than the active window, cutoff is the Nth latest user message
        cutoff_index = 0
        if len(user_indices) > window_turns:
            cutoff_index = user_indices[-window_turns]
        elif len(messages) > 8:
            # Autonomous agent trajectory: few user messages but multiple sequential tool turns.
            # Protect the most recent 6 messages (active working memory) while allowing
            # pruning of earlier execution outputs.
            cutoff_index = max(2, len(messages) - 6)

        for idx, msg in enumerate(messages):
            msg_copy = copy.deepcopy(msg)
            role = msg_copy.get("role", "")
            
            # System prompt, early conversation prefix anchor (idx <= 1), and messages within active window are preserved 100%
            # This ensures upstream Google Antigravity prefix cache byte boundary is never broken.
            if role == "system" or idx <= 1 or idx >= cutoff_index:
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
                            pruned_tool_count += 1
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
                                    p_diff = len(p_text) - len(part["text"])
                                    if p_diff > 0:
                                        total_pruned_chars += p_diff
                                        pruned_tool_count += 1
                        new_parts.append(part)
                    msg_copy["content"] = new_parts

            compacted.append(msg_copy)

        estimated_tokens_pruned = max(0, total_pruned_chars // 4)
        if estimated_tokens_pruned > 0:
            logger.info(
                f"[COMPACTOR] Pruned ~{estimated_tokens_pruned:,} tokens ({total_pruned_chars:,} chars) "
                f"across {pruned_tool_count} tool output(s) beyond last {window_turns} active turns."
            )

        stats = CompactorStats(
            tokens_saved=estimated_tokens_pruned,
            chars_saved=total_pruned_chars,
            pruned_tool_messages=pruned_tool_count
        )
        return compacted, stats
