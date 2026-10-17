import json
from typing import Dict, Any, Tuple, List
from ..config import SYSTEM_INSTRUCTION
from .schema_cleaner import clean_schema_for_antigravity

def resolve_model_name(raw_model: str) -> str:
    """Normalize client model names to Antigravity internal identifiers."""
    if not raw_model:
        return "claude-sonnet-4-6"
    m = raw_model.strip()
    # Strip prefix like google/ or antigravity/
    if "/" in m:
        m = m.split("/", 1)[1]
    m_lower = m.lower()
    if "claude-3-7-sonnet" in m_lower or "claude-sonnet-4" in m_lower:
        return "claude-sonnet-4-6"
    if "claude-opus" in m_lower:
        return "claude-opus-4-6-thinking"
    if "gemini-3.8-flash-high" in m_lower:
        return "gemini-3.8-flash-high"
    if "gemini-3.8-flash-low" in m_lower:
        return "gemini-3.8-flash-low"
    if "gemini-3.8-flash" in m_lower or "gemini-3-flash" in m_lower:
        return "gemini-3-flash"
    if "gemini-3.1-flash-lite" in m_lower:
        return "gemini-3.1-flash-lite"
    if "gemini-3.5-flash-lite" in m_lower:
        return "gemini-3.5-flash-lite"
    if "gpt-oss" in m_lower:
        return "gpt-oss-120b-medium"
    # Fallback legacy 2.5 models to gemini-3-flash to avoid 503 capacity errors
    if "gemini-2.5" in m_lower or "gemini-2" in m_lower:
        return "gemini-3-flash"
    return m

def transform_openai_to_antigravity(body: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Transform standard OpenAI Chat Completion request dictionary into Antigravity internal format."""
    model = resolve_model_name(body.get("model", ""))
    is_claude = "claude" in model.lower()
    is_claude_thinking = "opus" in model.lower() and "thinking" in model.lower()
    is_gemini3 = "gemini-3" in model.lower()

    contents = []
    system_texts = []
    tool_call_map = {}  # call_id -> function_name

    messages = body.get("messages", [])
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            if isinstance(content, str):
                system_texts.append(content)
            elif isinstance(content, list):
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text" and p.get("text"):
                        system_texts.append(p["text"])

        elif role == "user":
            parts = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for p in content:
                    if isinstance(p, dict):
                        if p.get("type") == "text" and p.get("text"):
                            parts.append({"text": p["text"]})
                        elif p.get("type") == "image_url" and isinstance(p.get("image_url"), dict):
                            url = p["image_url"].get("url", "")
                            if url.startswith("data:"):
                                try:
                                    meta, b64_data = url.split(";base64,")
                                    mime_type = meta.replace("data:", "")
                                    parts.append({"inlineData": {"mimeType": mime_type, "data": b64_data}})
                                except Exception:
                                    pass
            if parts:
                contents.append({"role": "user", "parts": parts})

        elif role == "assistant":
            parts = []
            if content and isinstance(content, str):
                parts.append({"text": content})

            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if tc.get("type") == "function" and "function" in tc:
                        fn = tc["function"]
                        fn_name = fn.get("name", "unknown")
                        call_id = tc.get("id", "")
                        if call_id:
                            tool_call_map[call_id] = fn_name

                        fn_args = fn.get("arguments", {})
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}

                        parts.append({
                            "functionCall": {
                                "name": fn_name,
                                "args": fn_args if isinstance(fn_args, dict) else {}
                            },
                            "thoughtSignature": "skip_thought_signature_validator"
                        })
            if parts:
                contents.append({"role": "model", "parts": parts})

        elif role in ("tool", "function"):
            call_id = msg.get("tool_call_id")
            fn_name = msg.get("name") or tool_call_map.get(call_id, "unknown_tool")
            out_val = msg.get("content", "")

            # Ensure response payload is ALWAYS a JSON Object (dict / google.protobuf.Struct)
            # Protobuf will reject lists at functionResponse.response with:
            # "Proto field is not repeating, cannot start list."
            response_dict = {}
            if isinstance(out_val, str):
                try:
                    parsed = json.loads(out_val)
                    if isinstance(parsed, dict):
                        response_dict = parsed
                    else:
                        response_dict = {"output": parsed}
                except Exception:
                    response_dict = {"output": out_val}
            elif isinstance(out_val, dict):
                response_dict = out_val
            else:
                response_dict = {"output": out_val if out_val is not None else ""}

            fn_part = {
                "functionResponse": {
                    "name": fn_name,
                    "response": response_dict
                }
            }

            # If preceding turn was already user containing functionResponse, merge parts for parallel tool calls
            if contents and contents[-1].get("role") == "user" and any("functionResponse" in p for p in contents[-1].get("parts", [])):
                contents[-1]["parts"].append(fn_part)
            else:
                contents.append({
                    "role": "user",
                    "parts": [fn_part]
                })

    # System instruction
    final_sys_parts = [SYSTEM_INSTRUCTION] + system_texts
    system_instruction = {
        "role": "user",
        "parts": [{"text": "\n\n".join([p for p in final_sys_parts if p])}]
    }

    # Tools
    tools = []
    raw_tools = body.get("tools")
    if isinstance(raw_tools, list) and raw_tools:
        declarations = []
        for t in raw_tools:
            if isinstance(t, dict) and t.get("type") == "function" and "function" in t:
                fn = t["function"]
                declarations.append({
                    "name": fn.get("name", "tool"),
                    "description": fn.get("description", ""),
                    "parameters": clean_schema_for_antigravity(fn.get("parameters"))
                })
        if declarations:
            tools.append({"functionDeclarations": declarations})

    # Generation config
    generation_config: Dict[str, Any] = {}
    if "temperature" in body and body["temperature"] is not None:
        generation_config["temperature"] = body["temperature"]
    if "top_p" in body and body["top_p"] is not None:
        generation_config["topP"] = body["top_p"]
    if "max_tokens" in body and body["max_tokens"] is not None:
        generation_config["maxOutputTokens"] = body["max_tokens"]

    if is_claude_thinking:
        generation_config["thinkingConfig"] = {
            "include_thoughts": True,
            "thinking_budget": 8192
        }
    elif is_gemini3:
        generation_config["thinkingConfig"] = {
            "includeThoughts": True,
            "thinkingLevel": "medium"
        }

    req_payload: Dict[str, Any] = {
        "contents": contents,
        "systemInstruction": system_instruction,
        "generationConfig": generation_config
    }

    if tools:
        req_payload["tools"] = tools
        if is_claude:
            req_payload["toolConfig"] = {
                "functionCallingConfig": {"mode": "VALIDATED"}
            }

    return model, req_payload
