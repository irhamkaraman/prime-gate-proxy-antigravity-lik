import json
import uuid
import time
from typing import Dict, Any, List, Optional

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

