import json
from typing import AsyncGenerator, Dict, Any, List, Optional

class MockAntigravityUpstream:
    """
    Deterministic offline mock for Google Antigravity upstream server.
    Emulates chunked SSE streaming, tool calls, thinking blocks, and usage metadata.
    """

    @classmethod
    async def stream_text_response(
        cls,
        text: str,
        thinking: Optional[str] = None,
        chunk_size: int = 15
    ) -> AsyncGenerator[str, None]:
        """Streams text and optional thinking block in SSE format."""
        if thinking:
            chunk = {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"thought": True, "text": thinking}]
                        }
                    }
                ]
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        words = text.split(" ")
        for i in range(0, len(words), 3):
            sub = " ".join(words[i:i+3])
            if i + 3 < len(words):
                sub += " "
            chunk = {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": sub}]
                        }
                    }
                ]
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Terminal chunk with finishReason and usage
        terminal_chunk = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": []},
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 20,
                "candidatesTokenCount": len(words),
                "totalTokenCount": 20 + len(words)
            }
        }
        yield f"data: {json.dumps(terminal_chunk)}\n\n"

    @classmethod
    async def stream_tool_call_response(
        cls,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Streams a function call execution response."""
        chunk = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "name": tool_name,
                                    "args": tool_args
                                }
                            }
                        ]
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 35,
                "candidatesTokenCount": 25,
                "totalTokenCount": 60
            }
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    @classmethod
    def get_non_stream_response(
        cls,
        text: str = "",
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Returns non-streaming JSON candidates structure."""
        parts: List[Dict[str, Any]] = []
        if tool_name and tool_args is not None:
            parts.append({
                "functionCall": {
                    "name": tool_name,
                    "args": tool_args
                }
            })
        if text:
            parts.append({"text": text})

        return {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": parts
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 18,
                "candidatesTokenCount": 42,
                "totalTokenCount": 60
            }
        }
