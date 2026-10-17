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
    finish_reason: str = "stop"
) -> Dict[str, Any]:
    """Format standard OpenAI non-streaming ChatCompletion response."""
    message: Dict[str, Any] = {
        "role": "assistant",
        "content": content_text if content_text else None
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"

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
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }
