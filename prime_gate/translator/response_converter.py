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

def normalize_tool_call(
    raw_fn_name: str,
    raw_args: Any,
    declared_tools: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Standardize tool names and parameter dictionaries across different AI agents
    (OpenCode, Continue, Cursor, Claude Code, Aider, etc.) and Google Antigravity backends.

    1. Resolves tool name aliases without overriding an already-matching declared tool.
    2. Maps common parameter aliases (path, content, command, old/new string).
    3. Guarantees required properties (like content: "") to prevent Zod schema crashes.
    4. Strips extraneous metadata that causes strict schema validators to reject calls.
    """
    # 1. Parse raw_args safely
    if isinstance(raw_args, str):
        try:
            parsed_args = json.loads(raw_args)
            if not isinstance(parsed_args, dict):
                parsed_args = {}
        except Exception:
            parsed_args = parse_antigravity_args(raw_args)
    elif isinstance(raw_args, dict):
        parsed_args = dict(raw_args)
    else:
        parsed_args = {}

    # 2. Sanitize function name
    fn_name = (raw_fn_name or "").strip()
    if fn_name.startswith("default_api:"):
        fn_name = fn_name.split(":", 1)[1]

    # 3. Build declared tool dictionary and case-insensitive lookup
    declared_names = {}
    lower_to_declared = {}
    if declared_tools and isinstance(declared_tools, list):
        for t in declared_tools:
            if isinstance(t, dict):
                name = t.get("function", {}).get("name") or t.get("name")
                if name:
                    declared_names[name] = t
                    lower_to_declared[name.lower()] = name

    # 4. Map tool names if not already matching declared tool
    fn_lower = fn_name.lower()
    if fn_name in declared_names:
        pass
    elif fn_lower in lower_to_declared:
        fn_name = lower_to_declared[fn_lower]
    else:
        if fn_lower in ("shell", "run_command", "exec", "terminal", "execute_command", "bash", "command"):
            for cand in ("bash", "shell", "run_command", "exec", "terminal", "execute_command"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break
        elif fn_lower in ("view_file", "read_file", "cat", "readfile", "read", "read_file_content", "view"):
            for cand in ("read_file", "read", "readfile", "view_file", "view", "read_file_content", "cat"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break
        elif fn_lower in ("edit_file", "edit", "replace_file_content", "str_replace_editor", "editfile", "replace"):
            for cand in ("edit_file", "edit", "replace_file_content", "str_replace_editor", "editfile", "replace"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break
        elif fn_lower in ("write_to_file", "write_file", "writefile", "write", "create_file"):
            for cand in ("write_file", "write", "writefile", "create_file", "write_to_file"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break
        elif fn_lower in ("list_dir", "list_files", "ls", "listfiles", "list", "directory_list", "glob", "find"):
            for cand in ("glob", "list_dir", "list_files", "list", "listfiles", "ls"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break

        # Cross-fallback between edit and write ONLY if one is missing entirely from declared tools
        if fn_lower in ("edit_file", "edit", "replace_file_content") and fn_name not in declared_names:
            for cand in ("write_file", "write", "writefile"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break
        elif fn_lower in ("write_to_file", "write_file", "write") and fn_name not in declared_names:
            for cand in ("edit_file", "edit"):
                if cand in lower_to_declared:
                    fn_name = lower_to_declared[cand]
                    break

    # 5. Parameter normalization and schema filtering
    if fn_name in declared_names:
        tool_def = declared_names[fn_name]
        params = tool_def.get("function", {}).get("parameters") or tool_def.get("parameters") or tool_def.get("input_schema") or {}
        props = params.get("properties") if isinstance(params, dict) else None
        required = set(params.get("required") or []) if isinstance(params, dict) else set()

        if props and isinstance(props, dict):
            # Command normalization
            if "cmd" in props:
                for alias in ("command", "CommandLine", "script", "input"):
                    if alias in parsed_args and "cmd" not in parsed_args:
                        parsed_args["cmd"] = parsed_args.pop(alias)
            if "command" in props:
                for alias in ("cmd", "CommandLine", "script", "input"):
                    if alias in parsed_args and "command" not in parsed_args:
                        parsed_args["command"] = parsed_args.pop(alias)

            # Path normalization
            for path_prop in ("path", "filePath", "file_path", "TargetFile", "target_file", "filepath", "file", "filename"):
                if path_prop in props:
                    for alias in ("AbsolutePath", "filePath", "file_path", "TargetFile", "target_file", "filepath", "path", "file", "filename"):
                        if alias != path_prop and alias in parsed_args and path_prop not in parsed_args:
                            parsed_args[path_prop] = parsed_args.pop(alias)

            # Content normalization
            for content_prop in ("content", "contents", "CodeContent", "code", "text", "data", "body", "file_text", "new_content"):
                if content_prop in props:
                    for alias in ("CodeContent", "content", "contents", "code", "text", "data", "body", "file_text", "new_content", "ReplacementContent"):
                        if alias != content_prop and alias in parsed_args and content_prop not in parsed_args:
                            parsed_args[content_prop] = parsed_args.pop(alias)

            # Edit normalization (diff / surgical search & replace)
            for old_prop in ("old_string", "pattern", "old_str", "search", "find", "target", "TargetContent"):
                if old_prop in props:
                    for alias in ("TargetContent", "old_string", "pattern", "old_str", "search", "find", "target"):
                        if alias != old_prop and alias in parsed_args and old_prop not in parsed_args:
                            parsed_args[old_prop] = parsed_args.pop(alias)

            for new_prop in ("new_string", "replacement", "new_str", "replace", "ReplacementContent"):
                if new_prop in props:
                    for alias in ("ReplacementContent", "new_string", "replacement", "new_str", "replace"):
                        if alias != new_prop and alias in parsed_args and new_prop not in parsed_args:
                            parsed_args[new_prop] = parsed_args.pop(alias)

            for mult_prop in ("replace_all", "AllowMultiple", "allow_multiple"):
                if mult_prop in props:
                    for alias in ("AllowMultiple", "allow_multiple", "replace_all"):
                        if alias != mult_prop and alias in parsed_args and mult_prop not in parsed_args:
                            parsed_args[mult_prop] = parsed_args.pop(alias)

            # Safety fallback for required keys to prevent client-side Zod validation failure
            for req_key in required:
                if req_key not in parsed_args:
                    if req_key in ("content", "contents", "CodeContent", "text", "data", "body"):
                        parsed_args[req_key] = ""
                    elif req_key in ("overwrite", "Overwrite"):
                        parsed_args[req_key] = True

            # Filter unrecognized properties (like toolAction, toolSummary, timeout, Instruction, Description)
            filtered_args = {k: v for k, v in parsed_args.items() if k in props}
            if filtered_args:
                parsed_args = filtered_args

    return fn_name, parsed_args

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

        # Normalize tool name and args against declared tools
        fn_name, parsed_args = normalize_tool_call(raw_name, raw_args, declared_tools)

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

