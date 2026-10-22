import copy
import logging
import re
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("prime_gate.compactor")

class CompactorStats(dict):
    """
    Statistics dictionary that also behaves as an integer (tokens_saved)
    for seamless backwards compatibility.
    """
    def __init__(
        self,
        tokens_saved: int = 0,
        chars_saved: int = 0,
        pruned_tool_messages: int = 0,
        dry_run: bool = False
    ):
        super().__init__({
            "compacted": tokens_saved > 0 or chars_saved > 0,
            "tokens_saved": tokens_saved,
            "chars_saved": chars_saved,
            "pruned_tool_messages": pruned_tool_messages,
            "dry_run": dry_run,
        })
        self.tokens_saved = tokens_saved
        self.dry_run = dry_run

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


class CompactedMessages(list):
    """
    List of messages that also carries compactor statistics.
    Provides seamless compatibility when treated directly as a list of dicts.
    """
    def __init__(self, items: List[Any], stats: Optional[CompactorStats] = None):
        super().__init__(items)
        self.stats = stats or CompactorStats()

    @property
    def tokens_saved(self) -> int:
        return self.stats.tokens_saved

    @property
    def chars_saved(self) -> int:
        return self.stats.get("chars_saved", 0)


class ContextCompactor:
    """
    Intelligent conversation context compactor for AI coding agents.
    
    Compresses excessive historical tool execution outputs (such as massive read_file,
    terminal command logs, and file listings) older than active working memory window
    to prevent 30k - 260k+ token blowups while preserving active working memory,
    system instructions, and prefix cache alignment.
    
    Fase 3B Invariants:
    1. Error logs (exit code != 0, Traceback, is_error=True) are NEVER pruned.
    2. Tool outputs referenced downstream in subsequent turns are NEVER pruned.
    3. Dry-run mode produces 100% byte-for-byte unmodified payloads while recording telemetry.
    4. Informative markers indicate '[output dipangkas: ~N token]' to the model.
    """

    DEFAULT_CONFIG = {
        "enabled": True,
        "window_turns": 3,
        "window_tools": 2,
        "max_tool_chars": 600,
        "preserve_head_lines": 4,
        "preserve_tail_lines": 4,
        "dry_run": False,
        "preserve_errors": True,
        "preserve_re_references": True,
        "client_overrides": {},
        "model_overrides": {},
    }

    ERROR_PATTERNS = [
        re.compile(r"exit (code|status)[:=\s]+[1-9]\d*", re.IGNORECASE),
        re.compile(r"returncode=[1-9]\d*", re.IGNORECASE),
        re.compile(r"traceback \(most recent call last\):", re.IGNORECASE),
        re.compile(r"\b(syntaxerror|typeerror|valueerror|nameerror|indexerror|keyerror|runtimeerror|assertionerror|filenotfounderror)\b:", re.IGNORECASE),
        re.compile(r"\bfatal error\b:", re.IGNORECASE),
        re.compile(r"\bcommand failed\b", re.IGNORECASE),
        re.compile(r"\bfailed to compile\b", re.IGNORECASE),
        re.compile(r"\bbuild failed\b", re.IGNORECASE),
        re.compile(r"\bexception in thread\b", re.IGNORECASE),
        re.compile(r"\bpanic:\b", re.IGNORECASE),
    ]

    @classmethod
    def resolve_config(
        cls,
        client_name: str = "",
        model_name: str = "",
        base_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolves hierarchical compactor configuration:
        DEFAULT_CONFIG <- base_config <- client_overrides <- model_overrides
        """
        cfg = dict(cls.DEFAULT_CONFIG)
        if base_config:
            cfg.update(base_config)

        client_norm = (client_name or "").lower().strip()
        model_norm = (model_name or "").lower().strip()

        # 1. Client overrides
        client_overrides = cfg.get("client_overrides") or {}
        if isinstance(client_overrides, dict) and client_norm:
            for pattern, c_cfg in client_overrides.items():
                if pattern.lower() in client_norm and isinstance(c_cfg, dict):
                    cfg.update(c_cfg)
                    break

        # 2. Model overrides
        model_overrides = cfg.get("model_overrides") or {}
        if isinstance(model_overrides, dict) and model_norm:
            for pattern, m_cfg in model_overrides.items():
                if pattern.lower() in model_norm and isinstance(m_cfg, dict):
                    cfg.update(m_cfg)
                    break

        return cfg

    @classmethod
    def _contains_error(cls, content: Any, is_error_flag: bool = False) -> bool:
        """
        Detects if tool output represents an execution error or failure.
        """
        if is_error_flag:
            return True
        if not content:
            return False
        if not isinstance(content, str):
            if isinstance(content, list):
                return any(cls._contains_error(item) for item in content)
            if isinstance(content, dict):
                return cls._contains_error(
                    content.get("content") or content.get("text", ""),
                    content.get("is_error", False)
                )
            return False

        lower_c = content.lower()
        if (
            "error" not in lower_c
            and "failed" not in lower_c
            and "exception" not in lower_c
            and "traceback" not in lower_c
            and "panic" not in lower_c
            and "exit" not in lower_c
            and "returncode" not in lower_c
        ):
            return False

        for pattern in cls.ERROR_PATTERNS:
            if pattern.search(content):
                return True
        return False

    @classmethod
    def _is_referenced_downstream(
        cls,
        tool_idx: int,
        messages: List[Dict[str, Any]],
        call_id: Optional[str] = None
    ) -> bool:
        """
        Detects if a tool execution is explicitly referenced or discussed
        in subsequent conversation turns.
        """
        if tool_idx >= len(messages) - 1:
            return False

        downstream = messages[tool_idx + 1:]

        # 1. Search for explicit call_id reference
        if call_id:
            for msg in downstream:
                c = msg.get("content", "")
                if isinstance(c, str) and call_id in c:
                    return True
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict):
                            t = part.get("text", "") or str(part.get("content", ""))
                            if call_id in t:
                                return True

        # 2. Search for tool function argument identifiers (e.g., target file paths)
        # Look backwards to find the assistant tool_call that triggered this tool
        target_identifiers = []
        if tool_idx > 0:
            prev_msg = messages[tool_idx - 1]
            if prev_msg.get("role") == "assistant":
                for tc in prev_msg.get("tool_calls", []):
                    if tc.get("id") == call_id:
                        fn = tc.get("function", {})
                        args_str = fn.get("arguments", "")
                        # Look for common file path arguments
                        paths = re.findall(r'"(?:path|file|filename|target)":\s*"([^"]+)"', args_str)
                        target_identifiers.extend(paths)

        if target_identifiers:
            for msg in downstream:
                c = msg.get("content", "")
                for target_id in target_identifiers:
                    if isinstance(c, str) and target_id in c:
                        return True
                    elif isinstance(c, list):
                        for part in c:
                            if isinstance(part, dict):
                                t = part.get("text", "") or str(part.get("content", ""))
                                if target_id in t:
                                    return True

        return False

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
    def _prune_string_content(
        cls,
        content: str,
        max_tool_chars: int,
        head_lines: int,
        tail_lines: int
    ) -> Tuple[str, int]:
        orig_len = len(content)
        if orig_len <= max_tool_chars:
            return content, 0

        lines = content.splitlines()
        orig_lines = len(lines)
        if orig_lines > (head_lines + tail_lines + 2):
            kept_head = lines[:head_lines]
            kept_tail = lines[-tail_lines:]
            # Compute estimated pruned tokens
            approx_pruned_chars = orig_len - (sum(len(l) for l in kept_head) + sum(len(l) for l in kept_tail))
            approx_pruned_tokens = max(1, approx_pruned_chars // 4)
            pruned_marker = (
                f"\n[output dipangkas: ~{approx_pruned_tokens:,} token | "
                f"Historical tool execution output pruned by Prime Gate Compactor "
                f"(Original: {orig_len:,} chars, {orig_lines} lines)]\n"
            )
            new_content = "\n".join(kept_head) + pruned_marker + "\n".join(kept_tail)
        else:
            half = max_tool_chars // 2
            approx_pruned_chars = orig_len - (half * 2)
            approx_pruned_tokens = max(1, approx_pruned_chars // 4)
            pruned_marker = (
                f"\n[output dipangkas: ~{approx_pruned_tokens:,} token | "
                f"Historical tool output pruned by Prime Gate Compactor "
                f"(Original: {orig_len:,} chars)]\n"
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
        client_name: str = "",
        model_name: str = "",
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], CompactorStats]:
        """
        Compacts OpenAI-format message history with intelligent error and re-reference protection.
        """
        cfg = cls.resolve_config(client_name=client_name, model_name=model_name, base_config=config)
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
        dry_run = bool(cfg.get("dry_run", False))
        preserve_errors = bool(cfg.get("preserve_errors", True))
        preserve_re_references = bool(cfg.get("preserve_re_references", True))

        # 1. Identify all tool output messages
        tool_indices = [i for i, m in enumerate(messages) if cls._is_tool_message(m)]
        # Protect the most recent window_tools tool executions
        protected_tool_indices = set(tool_indices[-window_tools:]) if (window_tools > 0 and len(tool_indices) > 0) else set()

        # 2. Check user turn cutoff for standard multi-turn dialogue
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
            call_id = msg_copy.get("tool_call_id")

            # Anchor system prompt and first turn (prefix cache boundary)
            if role == "system" or idx <= 1:
                compacted.append(msg_copy)
                continue

            # Active recent tool results are 100% protected in working memory
            is_active_tool = (idx in protected_tool_indices) and (user_cutoff == 0 or idx >= user_cutoff)
            if is_active_tool:
                compacted.append(msg_copy)
                continue

            # Check if this tool output contains an error (Invariant #1)
            if preserve_errors and cls._contains_error(msg_copy.get("content", "")):
                compacted.append(msg_copy)
                continue

            # Check if this tool output is referenced downstream (Invariant #2)
            if preserve_re_references and cls._is_referenced_downstream(idx, messages, call_id=call_id):
                compacted.append(msg_copy)
                continue

            # If it's a tool output message (OpenAI role: tool/function or user containing tool_result)
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
                            res_err = part.get("is_error", False)
                            t_use_id = part.get("tool_use_id")

                            if preserve_errors and cls._contains_error(res_content, is_error_flag=res_err):
                                new_parts.append(part)
                                continue

                            if preserve_re_references and cls._is_referenced_downstream(idx, messages, call_id=t_use_id):
                                new_parts.append(part)
                                continue

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
            mode_label = " (DRY-RUN)" if dry_run else ""
            logger.info(
                f"[COMPACTOR{mode_label}] Pruned ~{estimated_tokens_pruned:,} tokens ({total_pruned_chars:,} chars) "
                f"across {pruned_tool_count} tool output(s) older than last {window_tools} active tool steps."
            )

        stats = CompactorStats(
            tokens_saved=estimated_tokens_pruned,
            chars_saved=total_pruned_chars,
            pruned_tool_messages=pruned_tool_count,
            dry_run=dry_run
        )

        # Dry-run guarantee: return original messages without modification
        if dry_run:
            return copy.deepcopy(messages), stats

        return compacted, stats

    @classmethod
    def compact_anthropic_body_messages(
        cls,
        messages: List[Dict[str, Any]],
        window_tools: int = 2,
        max_tool_chars: int = 600,
        head_lines: int = 4,
        tail_lines: int = 4,
        dry_run: bool = False,
        preserve_errors: bool = True,
        preserve_re_references: bool = True,
        config: Optional[Dict[str, Any]] = None,
        client_name: str = "",
        model_name: str = ""
    ) -> Tuple[List[Dict[str, Any]], CompactorStats]:
        """
        Compacts Anthropic-format body['messages'] array directly.
        Prunes historical tool_result content blocks older than window_tools.
        """
        if not messages:
            return messages, CompactorStats()

        cfg = cls.resolve_config(client_name=client_name, model_name=model_name, base_config=config)
        window_tools = int(cfg.get("window_tools", window_tools))
        max_tool_chars = int(cfg.get("max_tool_chars", max_tool_chars))
        head_lines = int(cfg.get("preserve_head_lines", head_lines))
        tail_lines = int(cfg.get("preserve_tail_lines", tail_lines))
        dry_run = bool(cfg.get("dry_run", dry_run))
        preserve_errors = bool(cfg.get("preserve_errors", preserve_errors))
        preserve_re_references = bool(cfg.get("preserve_re_references", preserve_re_references))

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
                        is_err = block.get("is_error", False)
                        t_id = block.get("tool_use_id")

                        # Preserve errors
                        if preserve_errors and cls._contains_error(raw_c, is_error_flag=is_err):
                            new_blocks.append(block)
                            continue

                        # Preserve downstream references
                        if preserve_re_references and cls._is_referenced_downstream(m_idx, messages, call_id=t_id):
                            new_blocks.append(block)
                            continue

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

        estimated_tokens = max(0, total_pruned_chars // 4)
        if total_pruned_chars > 0:
            mode_lbl = " (DRY-RUN)" if dry_run else ""
            logger.info(
                f"[COMPACTOR (ANTHROPIC RAW){mode_lbl}] Pruned {pruned_count} tool_result blocks, "
                f"saving ~{total_pruned_chars:,} chars (~{estimated_tokens:,} tokens)."
            )

        stats = CompactorStats(
            tokens_saved=estimated_tokens,
            chars_saved=total_pruned_chars,
            pruned_tool_messages=pruned_count,
            dry_run=dry_run
        )

        if dry_run:
            return CompactedMessages(copy.deepcopy(messages), stats)

        return CompactedMessages(compacted_msgs, stats)
