"""
Context-Aware Cache Key Extractor for Prime Gate.
Provides deterministic context-based keying, scope isolation (per API key / project),
and strict context hashing over system prompts, conversation history, tool results,
and generation parameters.
"""

import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple


class ContextKeyExtractor:
    """
    Extracts and computes a deterministic context-aware cache tuple:
    (cache_key, context_hash, last_user_query, query_hash, tools_sig, scope, has_tools)

    Invariance:
    If two requests share the exact same user query but differ in:
    - system prompt / system instructions
    - conversation history (prior turns)
    - referenced files or tool execution outputs
    - declared tool definitions
    - generation parameters (model, temperature)
    -> context_hash WILL DIFFER, completely preventing cross-context false hits.
    """

    @staticmethod
    def extract_text_content(content: Any) -> str:
        """Extracts plain text from string or structured content block lists."""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_result":
                        # Anthropic tool result block
                        res_content = item.get("content", "")
                        text_parts.append(f"[tool_result:{item.get('tool_use_id', '')}]:{res_content}")
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts).strip()
        return str(content).strip() if content is not None else ""

    @classmethod
    def compute(
        cls,
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[Any] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        generation_params: Optional[Dict[str, Any]] = None,
        api_key_prefix: str = "default",
        project_id: Optional[str] = None
    ) -> Tuple[str, str, str, str, str, str, bool]:
        """
        Computes context-aware cache metadata.

        Returns:
            Tuple of:
            - cache_key: Complete exact-match key string
            - context_hash: 32-char SHA-256 hash of context dependencies
            - last_user_query: Clean text of the last user query
            - query_hash: 32-char SHA-256 hash of the last user query
            - tools_signature: Sorted comma-separated list of tool names
            - scope: Scope partition identifier (e.g. 'pg-live-a1b2:default')
            - has_tools: Boolean indicating whether tools are declared
        """
        scope = f"{api_key_prefix}:{project_id or 'default'}"

        # 1. System Prompt Extraction
        system_texts: List[str] = []
        if system_prompt:
            sys_str = cls.extract_text_content(system_prompt)
            if sys_str:
                system_texts.append(sys_str)

        # 2. Conversation Traversal & Turn Separation
        history_turns: List[Dict[str, Any]] = []
        last_user_idx = -1

        for idx, msg in enumerate(messages):
            role = msg.get("role", "")
            if role in ("system", "developer"):
                sys_part = cls.extract_text_content(msg.get("content"))
                if sys_part:
                    system_texts.append(sys_part)
            elif role == "user":
                last_user_idx = idx

        last_user_query = ""
        for idx, msg in enumerate(messages):
            role = msg.get("role", "")
            if role in ("system", "developer"):
                continue

            content_text = cls.extract_text_content(msg.get("content"))

            # Capture tool_calls in assistant messages
            tool_calls = msg.get("tool_calls")
            norm_tool_calls = []
            if tool_calls and isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        norm_tool_calls.append({
                            "name": fn.get("name", "") if isinstance(fn, dict) else "",
                            "arguments": fn.get("arguments", "") if isinstance(fn, dict) else ""
                        })

            if idx == last_user_idx:
                last_user_query = content_text
            else:
                history_turns.append({
                    "role": role,
                    "content": content_text,
                    "tool_calls": norm_tool_calls,
                    "tool_call_id": msg.get("tool_call_id", "")
                })

        # 3. Normalized Tools Signature & Schema Fingerprint
        tools_list: List[Dict[str, Any]] = []
        tools_names: List[str] = []
        has_tools = False

        if tools and isinstance(tools, list) and len(tools) > 0:
            has_tools = True
            for t in tools:
                if isinstance(t, dict):
                    fn = t.get("function") if isinstance(t.get("function"), dict) else t
                    name = fn.get("name", "")
                    if name:
                        tools_names.append(name)
                        # Canonical schema serialization
                        params = fn.get("parameters", {})
                        tools_list.append({
                            "name": name,
                            "parameters": params
                        })
            tools_list.sort(key=lambda x: x["name"])
            tools_names.sort()

        tools_sig = ",".join(tools_names)

        # 4. Filter Generation Parameters
        filtered_params: Dict[str, Any] = {}
        if generation_params:
            for p in ("temperature", "top_p", "presence_penalty", "frequency_penalty"):
                val = generation_params.get(p)
                if val is not None:
                    # Round float to 3 decimal places to normalize float variances
                    filtered_params[p] = round(float(val), 3) if isinstance(val, (int, float)) else val

        # 5. Compute Deterministic Context Hash
        context_payload = {
            "model": model,
            "system": "\n---\n".join(system_texts),
            "history": history_turns,
            "tools": tools_list,
            "params": filtered_params
        }
        canonical_context_json = json.dumps(context_payload, sort_keys=True, separators=(",", ":"))
        context_hash = hashlib.sha256(canonical_context_json.encode("utf-8")).hexdigest()[:32]

        # 6. Compute Query Hash and Cache Key
        normalized_query = last_user_query.strip().lower()
        query_hash = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()[:32]

        # Exact match cache key incorporates scope, model, context_hash, and query_hash
        cache_key = f"cache:{scope}:{model}:{context_hash}:{query_hash}"

        return cache_key, context_hash, last_user_query, query_hash, tools_sig, scope, has_tools
