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
    """
    if not text or "call:" not in text:
        return text, []

    pattern = r'call:(?:[a-zA-Z0-9_\-]+:)?([a-zA-Z0-9_\-]+)\s*(\{.*?\})'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    if not matches:
        return text, []

    tool_calls = []
    cleaned_text = text
    declared_names = {}
    if declared_tools and isinstance(declared_tools, list):
        for t in declared_tools:
            if isinstance(t, dict):
                fn_name = t.get("function", {}).get("name") or t.get("name")
                if fn_name:
                    declared_names[fn_name] = t

    for i, m in enumerate(matches):
        raw_name = m.group(1).strip()
        raw_args = m.group(2).strip()
        
        fn_name = raw_name
        # If model called default_api:shell or shell, but client declared 'bash', map it!
        if fn_name in ("shell", "run_command", "exec", "terminal"):
            for cand in ("bash", "shell", "run_command", "exec", "terminal", "execute_command"):
                if cand in declared_names:
                    fn_name = cand
                    break

        parsed_args = parse_antigravity_args(raw_args)

        tool_calls.append({
            "index": i,
            "id": f"call_pg_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": fn_name,
                "arguments": json.dumps(parsed_args)
            }
        })
        cleaned_text = cleaned_text.replace(m.group(0), "").strip()

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

