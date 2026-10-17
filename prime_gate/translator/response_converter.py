import re
import json
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple

def parse_antigravity_args(raw: str) -> Dict[str, Any]:
    """Parse Antigravity key:value or JSON arguments into a standard Python dict."""
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1].strip()
    
    # Try standard JSON first
    try:
        return json.loads("{" + raw + "}")
    except Exception:
        pass

    args = {}
    i = 0
    n = len(raw)
    
    while i < n:
        while i < n and (raw[i].isspace() or raw[i] == ','):
            i += 1
        if i >= n:
            break
            
        key_start = i
        while i < n and (raw[i].isalnum() or raw[i] in ('_', '-')):
            i += 1
        key = raw[key_start:i].strip()
        
        while i < n and raw[i].isspace():
            i += 1
        if i < n and raw[i] in (':', '='):
            i += 1
        while i < n and raw[i].isspace():
            i += 1
        if i >= n:
            break
            
        val = ""
        if raw[i] in ('"', "'"):
            quote_char = raw[i]
            i += 1
            val_start = i
            while i < n:
                if raw[i] == '\\' and i + 1 < n:
                    i += 2
                    continue
                if raw[i] == quote_char:
                    break
                i += 1
            val = raw[val_start:i]
            if i < n and raw[i] == quote_char:
                i += 1
        else:
            val_start = i
            while i < n and raw[i] not in (',', '}'):
                i += 1
            val = raw[val_start:i].strip()
            
        if val.isdigit():
            val = int(val)
        elif val.lower() == "true":
            val = True
        elif val.lower() == "false":
            val = False
        else:
            if '\\' in val:
                try:
                    val = val.encode().decode('unicode_escape')
                except Exception:
                    pass
            
        if key:
            args[key] = val
            
    return args

def extract_text_tool_calls(
    text: str,
    declared_tools: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Detects if the model emitted Antigravity text-based tool calls such as:
    call:default_api:shell{command: "...", timeout: 30000} or call:bash{...}
    and converts them into valid OpenAI tool_calls dicts.
    Handles balanced braces, nested JSON, tool name mapping, and parameter filtering.
    """
    if not text or "call:" not in text:
        return text, []

    declared_names = {}
    if declared_tools and isinstance(declared_tools, list):
        for t in declared_tools:
            if isinstance(t, dict):
                fn_name = t.get("function", {}).get("name") or t.get("name")
                if fn_name:
                    declared_names[fn_name] = t

    header_pattern = re.compile(r'call:(?:[a-zA-Z0-9_\-]+:)?([a-zA-Z0-9_\-]+)\s*\{')
    pos = 0
    tool_calls = []
    cleaned_parts = []
    call_idx = 0

    while pos < len(text):
        m = header_pattern.search(text, pos)
        if not m:
            cleaned_parts.append(text[pos:])
            break

        cleaned_parts.append(text[pos:m.start()])
        raw_name = m.group(1).strip()
        brace_start = m.end() - 1

        # Balanced brace scan
        depth = 0
        in_str = False
        quote_char = ''
        escape = False
        brace_end = -1

        for i in range(brace_start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if in_str:
                if ch == quote_char:
                    in_str = False
                continue
            if ch in ('"', "'"):
                in_str = True
                quote_char = ch
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break

        if brace_end == -1:
            cleaned_parts.append(text[m.start():])
            break

        raw_args = text[brace_start:brace_end + 1]
        pos = brace_end + 1

        # Tool name mapping
        fn_name = raw_name
        if fn_name in ("shell", "run_command", "exec", "terminal"):
            for cand in ("bash", "shell", "run_command", "exec", "terminal", "execute_command"):
                if cand in declared_names:
                    fn_name = cand
                    break
        elif fn_name in ("view_file", "read_file", "cat", "readFile", "read"):
            for cand in ("read_file", "read", "readFile", "view_file", "cat"):
                if cand in declared_names:
                    fn_name = cand
                    break
        elif fn_name in ("write_to_file", "write_file", "edit_file", "writeFile", "write", "edit"):
            for cand in ("write_file", "write", "writeFile", "edit_file", "edit", "write_to_file"):
                if cand in declared_names:
                    fn_name = cand
                    break
        elif fn_name in ("list_dir", "list_files", "ls", "listFiles", "list"):
            for cand in ("list_dir", "list_files", "list", "listFiles", "ls"):
                if cand in declared_names:
                    fn_name = cand
                    break

        parsed_args = parse_antigravity_args(raw_args)

        # Filter args against declared properties if known
        if fn_name in declared_names:
            tool_def = declared_names[fn_name]
            params = tool_def.get("function", {}).get("parameters") or tool_def.get("parameters") or {}
            props = params.get("properties") if isinstance(params, dict) else None
            if props and isinstance(props, dict):
                # Normalize common parameter aliases
                if "cmd" in props and "command" in parsed_args and "cmd" not in parsed_args:
                    parsed_args["cmd"] = parsed_args.pop("command")
                elif "command" in props and "cmd" in parsed_args and "command" not in parsed_args:
                    parsed_args["command"] = parsed_args.pop("cmd")

                if "path" in props:
                    for alias in ("AbsolutePath", "filePath", "file_path", "TargetFile", "target_file"):
                        if alias in parsed_args and "path" not in parsed_args:
                            parsed_args["path"] = parsed_args.pop(alias)

                if "content" in props:
                    for alias in ("CodeContent", "code", "text"):
                        if alias in parsed_args and "content" not in parsed_args:
                            parsed_args["content"] = parsed_args.pop(alias)

                # Filter out unrecognized properties (like timeout) so strict schema validators don't crash
                filtered_args = {k: v for k, v in parsed_args.items() if k in props}
                if filtered_args:
                    parsed_args = filtered_args

        tool_calls.append({
            "index": call_idx,
            "id": f"call_pg_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": fn_name,
                "arguments": json.dumps(parsed_args)
            }
        })
        call_idx += 1

    cleaned_text = "".join(cleaned_parts).strip()
    return cleaned_text, tool_calls


def format_sse_chunk(
    completion_id: str,
    created: int,
    model: str,
    delta: Dict[str, Any],
    finish_reason: Optional[str] = None
) -> str:
    """Format single OpenAI SSE chunk string."""
    chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason
            }
        ]
    }
    return f"data: {json.dumps(chunk)}\n\n"

def format_non_stream_response(
    completion_id: str,
    created: int,
    model: str,
    content_text: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    finish_reason: str = "stop",
    reasoning_content: Optional[str] = None,
    usage: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """Format standard OpenAI non-streaming ChatCompletion response."""
    message: Dict[str, Any] = {
        "role": "assistant",
        "content": content_text if content_text else ""
    }
    if reasoning_content:
        message["reasoning_content"] = reasoning_content
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"

    p_tok = usage.get("prompt_tokens", 0) if usage else 0
    c_tok = usage.get("completion_tokens", 0) if usage else 0
    t_tok = usage.get("total_tokens", p_tok + c_tok) if usage else (p_tok + c_tok)

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason
            }
        ],
        "usage": {
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "total_tokens": t_tok,
            "reasoning_tokens": usage.get("reasoning_tokens", 0) if usage else 0
        }
    }

