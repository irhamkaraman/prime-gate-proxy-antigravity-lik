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
    terminal command logs, and file listings) older than active working memory window
    to prevent 30k - 260k+ token blowups while preserving active working memory,
    system instructions, and prefix cache alignment.
    """

    DEFAULT_CONFIG = {
        "enabled": True,
        "window_turns": 3,
        "window_tools": 2,
        "max_tool_chars": 600,
        "preserve_head_lines": 4,
        "preserve_tail_lines": 4,
    }

    @staticmethod
    def _is_tool_message(msg: Dict[str, Any]) -> bool:
        role = msg.get("role", "")
        if role in ("tool", "function") or "tool_call_id" in msg:
            return True
        if role == "user":
            content = msg.get("content")
            if isinstance(content, list) and any(
                isinstance(p, dict) and p.get("type") == "tool_result" for p in content
            ):
                return True
        return False

    @classmethod
    def _prune_string_content(cls, content: str, max_tool_chars: int, head_lines: int, tail_lines: int) -> Tuple[str, int]:
        orig_len = len(content)
        if orig_len <= max_tool_chars:
            return content, 0

        lines = content.splitlines()
        orig_lines = len(lines)
        if orig_lines > (head_lines + tail_lines + 2):
            kept_head = lines[:head_lines]
            kept_tail = lines[-tail_lines:]
            pruned_marker = (
                f"\n[... Historical tool execution output pruned by Prime Gate Compactor "
                f"(Original: {orig_len:,} chars, {orig_lines} lines) ...]\n"
            )
            new_content = "\n".join(kept_head) + pruned_marker + "\n".join(kept_tail)
        else:
            half = max_tool_chars // 2
            pruned_marker = (
                f"\n[... Historical tool output pruned by Prime Gate Compactor "
                f"(Original: {orig_len:,} chars) ...]\n"
            )
            new_content = content[:half] + pruned_marker + content[-half:]

        pruned_diff = orig_len - len(new_content)
        if pruned_diff > 0:
            return new_content, pruned_diff
        return content, 0

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
        Compacts OpenAI-format message history.
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
        window_tools = int(cfg.get("window_tools", 2))
        max_tool_chars = int(cfg.get("max_tool_chars", 600))
        head_lines = int(cfg.get("preserve_head_lines", 4))
        tail_lines = int(cfg.get("preserve_tail_lines", 4))

        # 1. Identify all tool output messages
        tool_indices = [i for i, m in enumerate(messages) if cls._is_tool_message(m)]
        # Protect the most recent window_tools tool executions
        protected_tool_indices = set(tool_indices[-window_tools:]) if (window_tools > 0 and len(tool_indices) > 0) else set()

        # 2. Also check user turn cutoff for standard multi-turn dialogue
        user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user" and not cls._is_tool_message(m)]
        user_cutoff = 0
        if len(user_indices) > window_turns:
            user_cutoff = user_indices[-window_turns]

        total_pruned_chars = 0
        pruned_tool_count = 0
        compacted: List[Dict[str, Any]] = []

        for idx, msg in enumerate(messages):
            msg_copy = copy.deepcopy(msg)
            role = msg_copy.get("role", "")

            # Anchor system prompt and first turn (prefix cache boundary)
            if role == "system" or idx <= 1:
                compacted.append(msg_copy)
                continue

            # Active recent tool results are 100% protected in working memory
            is_active_tool = (idx in protected_tool_indices) and (user_cutoff == 0 or idx >= user_cutoff)
            if is_active_tool:
                compacted.append(msg_copy)
                continue

            # If it's a tool output message (either OpenAI role: tool or user containing tool_result)
            if role in ("tool", "function") or "tool_call_id" in msg_copy:
                content = msg_copy.get("content", "")
                if isinstance(content, str):
                    new_content, diff = cls._prune_string_content(content, max_tool_chars, head_lines, tail_lines)
                    if diff > 0:
                        total_pruned_chars += diff
                        pruned_tool_count += 1
                        msg_copy["content"] = new_content
                elif isinstance(content, list):
                    new_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            p_text = part.get("text", "")
                            p_new, p_diff = cls._prune_string_content(p_text, max_tool_chars, head_lines, tail_lines)
                            if p_diff > 0:
                                total_pruned_chars += p_diff
                                pruned_tool_count += 1
                                part["text"] = p_new
                        new_parts.append(part)
                    msg_copy["content"] = new_parts

            elif role == "user":
                content = msg_copy.get("content")
                if isinstance(content, list):
                    new_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "tool_result":
                            res_content = part.get("content", "")
                            if isinstance(res_content, str):
                                new_res, diff = cls._prune_string_content(res_content, max_tool_chars, head_lines, tail_lines)
                                if diff > 0:
                                    total_pruned_chars += diff
                                    pruned_tool_count += 1
                                    part["content"] = new_res
                        new_parts.append(part)
                    msg_copy["content"] = new_parts

            compacted.append(msg_copy)

        estimated_tokens_pruned = max(0, total_pruned_chars // 4)
        if estimated_tokens_pruned > 0:
            logger.info(
                f"[COMPACTOR] Pruned ~{estimated_tokens_pruned:,} tokens ({total_pruned_chars:,} chars) "
                f"across {pruned_tool_count} tool output(s) older than last {window_tools} active tool steps."
            )

        stats = CompactorStats(
            tokens_saved=estimated_tokens_pruned,
            chars_saved=total_pruned_chars,
            pruned_tool_messages=pruned_tool_count
        )
        return compacted, stats

    @classmethod
    def compact_anthropic_body_messages(
        cls,
        messages: List[Dict[str, Any]],
        window_tools: int = 2,
        max_tool_chars: int = 600,
        head_lines: int = 4,
        tail_lines: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Compacts Anthropic-format body['messages'] array directly.
        Prunes historical tool_result content blocks older than window_tools.
        """
        if not messages:
            return messages

        # 1. Locate all tool_result block occurrences: (message_idx, block_idx)
        tool_locations: List[Tuple[int, int]] = []
        for m_idx, msg in enumerate(messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    for b_idx, block in enumerate(content):
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_locations.append((m_idx, b_idx))

        # Protect the last window_tools tool_results
        protected_locations = set(tool_locations[-window_tools:]) if (window_tools > 0 and len(tool_locations) > 0) else set()

        compacted_msgs: List[Dict[str, Any]] = []
        total_pruned_chars = 0
        pruned_count = 0

        for m_idx, msg in enumerate(messages):
            msg_copy = copy.deepcopy(msg)
            if msg_copy.get("role") == "user" and isinstance(msg_copy.get("content"), list):
                new_blocks = []
                for b_idx, block in enumerate(msg_copy["content"]):
                    if (m_idx, b_idx) in protected_locations:
                        new_blocks.append(block)
                        continue

                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        raw_c = block.get("content", "")
                        if isinstance(raw_c, str):
                            new_c, diff = cls._prune_string_content(raw_c, max_tool_chars, head_lines, tail_lines)
                            if diff > 0:
                                total_pruned_chars += diff
                                pruned_count += 1
                                block["content"] = new_c
                        elif isinstance(raw_c, list):
                            new_sub = []
                            for sub in raw_c:
                                if isinstance(sub, dict) and sub.get("type") == "text":
                                    s_text = sub.get("text", "")
                                    s_new, diff = cls._prune_string_content(s_text, max_tool_chars, head_lines, tail_lines)
                                    if diff > 0:
                                        total_pruned_chars += diff
                                        pruned_count += 1
                                        sub["text"] = s_new
                                new_sub.append(sub)
                            block["content"] = new_sub
                    new_blocks.append(block)
                msg_copy["content"] = new_blocks

            compacted_msgs.append(msg_copy)

        if total_pruned_chars > 0:
            logger.info(
                f"[COMPACTOR (ANTHROPIC RAW)] Pruned {pruned_count} tool_result blocks, "
                f"saving ~{total_pruned_chars:,} chars (~{total_pruned_chars//4:,} tokens)."
            )

        return compacted_msgs
