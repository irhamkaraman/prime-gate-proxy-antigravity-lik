import json
import uuid
import time
import asyncio
import logging
import hashlib
from typing import Dict, Any, Tuple, List, Optional, AsyncGenerator

import httpx

from ..config import SYSTEM_INSTRUCTION
from ..resilience import AccountFailoverPool
from ..auth import get_access_token
from ..telemetry import telemetry
from ..db import db
from ..db.events import event_bus
from .schema_cleaner import clean_schema_for_antigravity
from .request_converter import resolve_model_info
from ..quota.monitor import QuotaMonitor

logger = logging.getLogger("prime_gate.translator.anthropic_converter")

ANTIGRAVITY_ENDPOINT = "https://daily-cloudcode-pa.sandbox.googleapis.com"


def format_anthropic_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format a strict Anthropic-compliant Server-Sent Event (SSE)."""
    return f"event: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def anthropic_to_openai_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalizes Anthropic request body (top-level system + messages array)
    into standard OpenAI-style message objects.
    This enables reusing ContextCompactor, AgentLoopGuard, and CacheKey computation.
    """
    normalized: List[Dict[str, Any]] = []

    # 1. Top-level system prompt
    raw_system = body.get("system")
    if raw_system:
        if isinstance(raw_system, str) and raw_system.strip():
            normalized.append({"role": "system", "content": raw_system.strip()})
        elif isinstance(raw_system, list):
            sys_parts = []
            for b in raw_system:
                if isinstance(b, dict) and b.get("type") == "text":
                    sys_parts.append(b.get("text", ""))
                elif isinstance(b, str):
                    sys_parts.append(b)
            if sys_parts:
                normalized.append({"role": "system", "content": "\n\n".join(sys_parts)})

    # 2. Messages array
    raw_messages = body.get("messages", [])
    if isinstance(raw_messages, list):
        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, str):
                normalized.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Anthropic content blocks: text, image, tool_use, tool_result
                text_parts = []
                tool_calls = []

                for block in content:
                    if not isinstance(block, dict):
                        if isinstance(block, str):
                            text_parts.append(block)
                        continue

                    b_type = block.get("type")
                    if b_type == "text":
                        text_parts.append(block.get("text", ""))
                    elif b_type == "tool_use":
                        tool_calls.append({
                            "id": block.get("id", f"toolu_{uuid.uuid4().hex[:12]}"),
                            "type": "function",
                            "function": {
                                "name": block.get("name", "unknown_tool"),
                                "arguments": json.dumps(block.get("input", {}))
                            }
                        })
                    elif b_type == "tool_result":
                        # Tool result in Anthropic is sent inside a user turn
                        tool_use_id = block.get("tool_use_id", "")
                        res_content = block.get("content", "")
                        if isinstance(res_content, list):
                            res_str = "".join([c.get("text", "") for c in res_content if isinstance(c, dict)])
                        else:
                            res_str = str(res_content)

                        normalized.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": res_str
                        })

                if text_parts or tool_calls:
                    msg_obj: Dict[str, Any] = {
                        "role": role,
                        "content": "\n".join(text_parts) if text_parts else None
                    }
                    if tool_calls:
                        msg_obj["tool_calls"] = tool_calls
                    normalized.append(msg_obj)

    return normalized


def transform_anthropic_to_antigravity(
    body: Dict[str, Any],
    account: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Translates an Anthropic /v1/messages request body into Google Antigravity format.
    Returns: (resolved_model, antigravity_request_payload)
    """
    account_email = account.get("email") if isinstance(account, dict) else None
    model, model_spec = resolve_model_info(body.get("model", ""), account_email=account_email)

    contents: List[Dict[str, Any]] = []
    system_texts: List[str] = []
    tool_call_map: Dict[str, str] = {}  # tool_use_id -> name

    # 1. Extract System Instruction
    raw_system = body.get("system")
    if raw_system:
        if isinstance(raw_system, str) and raw_system.strip():
            system_texts.append(raw_system.strip())
        elif isinstance(raw_system, list):
            for b in raw_system:
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                    system_texts.append(b["text"])
                elif isinstance(b, str) and b.strip():
                    system_texts.append(b.strip())

    # 2. Extract Messages
    raw_messages = body.get("messages", [])
    for msg in raw_messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content", "")

        target_role = "user" if role == "user" else "model"
        parts: List[Dict[str, Any]] = []

        if isinstance(content, str):
            if content:
                parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    if isinstance(block, str) and block:
                        parts.append({"text": block})
                    continue

                b_type = block.get("type")
                if b_type == "text":
                    txt = block.get("text", "")
                    if txt:
                        parts.append({"text": txt})

                elif b_type == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        mime_type = source.get("media_type", "image/png")
                        data_b64 = source.get("data", "")
                        if data_b64:
                            parts.append({
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": data_b64
                                }
                            })

                elif b_type == "tool_use":
                    call_id = block.get("id", f"toolu_{uuid.uuid4().hex[:12]}")
                    fn_name = block.get("name", "unknown_tool")
                    tool_call_map[call_id] = fn_name

                    raw_input = block.get("input", {})
                    if not isinstance(raw_input, dict):
                        raw_input = {"input": raw_input}

                    parts.append({
                        "functionCall": {
                            "name": fn_name,
                            "args": raw_input,
                            "id": call_id
                        },
                        "thoughtSignature": "skip_thought_signature_validator"
                    })

                elif b_type == "tool_result":
                    call_id = block.get("tool_use_id", "")
                    fn_name = tool_call_map.get(call_id, "unknown_tool")
                    raw_res = block.get("content", "")

                    response_dict: Dict[str, Any] = {}
                    if isinstance(raw_res, dict):
                        response_dict = raw_res
                    elif isinstance(raw_res, list):
                        text_collected = []
                        for sub_b in raw_res:
                            if isinstance(sub_b, dict) and sub_b.get("type") == "text":
                                text_collected.append(sub_b.get("text", ""))
                            elif isinstance(sub_b, str):
                                text_collected.append(sub_b)
                        response_dict = {"output": "\n".join(text_collected)}
                    elif isinstance(raw_res, str):
                        try:
                            parsed = json.loads(raw_res)
                            if isinstance(parsed, dict):
                                response_dict = parsed
                            else:
                                response_dict = {"output": parsed}
                        except Exception:
                            response_dict = {"output": raw_res}
                    else:
                        response_dict = {"output": str(raw_res) if raw_res is not None else ""}

                    if block.get("is_error"):
                        response_dict["is_error"] = True

                    fn_resp_part = {
                        "functionResponse": {
                            "name": fn_name,
                            "response": response_dict,
                            "id": call_id
                        }
                    }

                    # In Antigravity/Gemini, tool responses must be in user role.
                    if target_role == "user":
                        parts.append(fn_resp_part)
                    else:
                        # Append as separate user turn
                        contents.append({"role": "user", "parts": [fn_resp_part]})

        if parts:
            # If consecutive turn has same role, merge parts to satisfy Antigravity protocol
            if contents and contents[-1]["role"] == target_role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": target_role, "parts": parts})

    # System instruction
    if system_texts:
        system_instruction = {
            "role": "user",
            "parts": [{"text": "\n\n".join([t for t in system_texts if t])}]
        }
    else:
        system_instruction = {
            "role": "user",
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        }

    # Tools definition
    tools_list = []
    raw_tools = body.get("tools")
    if isinstance(raw_tools, list) and raw_tools:
        declarations = []
        for t in raw_tools:
            if not isinstance(t, dict):
                continue
            name = t.get("name", "tool")
            description = t.get("description", "")
            input_schema = t.get("input_schema") or t.get("parameters") or {}
            cleaned_params = clean_schema_for_antigravity(input_schema)
            declarations.append({
                "name": name,
                "description": description,
                "parameters": cleaned_params
            })
        if declarations:
            # Deterministic sorting by function name ensures consistent upstream byte prefix caching
            declarations.sort(key=lambda d: d.get("name", ""))
            tools_list.append({"functionDeclarations": declarations})

    # Tool choice
    tool_config = None
    raw_tc = body.get("tool_choice")
    if isinstance(raw_tc, dict):
        tc_type = raw_tc.get("type", "auto")
        if tc_type == "auto":
            tool_config = {"functionCallingConfig": {"mode": "AUTO"}}
        elif tc_type == "any":
            tool_config = {"functionCallingConfig": {"mode": "ANY"}}
        elif tc_type == "tool":
            fn_name = raw_tc.get("name")
            if fn_name:
                tool_config = {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [fn_name]
                    }
                }

    # Generation config
    generation_config: Dict[str, Any] = {}
    if "max_tokens" in body and body["max_tokens"] is not None:
        generation_config["maxOutputTokens"] = int(body["max_tokens"])
    if "temperature" in body and body["temperature"] is not None:
        generation_config["temperature"] = float(body["temperature"])
    if "top_p" in body and body["top_p"] is not None:
        generation_config["topP"] = float(body["top_p"])
    if "top_k" in body and body["top_k"] is not None:
        generation_config["topK"] = int(body["top_k"])
    if "stop_sequences" in body and isinstance(body["stop_sequences"], list):
        generation_config["stopSequences"] = body["stop_sequences"]

    # Anthropic Extended Thinking & Reasoning Effort Support
    raw_thinking = body.get("thinking")
    effort = str(body.get("reasoning_effort") or body.get("effort") or "").lower().strip()
    thinking_cfg: Optional[Dict[str, Any]] = None

    if isinstance(raw_thinking, dict) and raw_thinking.get("type") in ("enabled", "adaptive"):
        thinking_cfg = {"includeThoughts": True}
        budget = raw_thinking.get("budget_tokens")
        if budget and isinstance(budget, int) and budget > 0:
            thinking_cfg["thinkingBudget"] = budget
        if model_spec.get("thinking_level") in ["low", "medium", "high"]:
            thinking_cfg["thinkingLevel"] = model_spec["thinking_level"]
    elif effort in ("low", "medium", "high"):
        thinking_cfg = {"includeThoughts": True, "thinkingLevel": effort}
        if effort == "low":
            thinking_cfg["thinkingBudget"] = 1000
        elif effort == "medium":
            thinking_cfg["thinkingBudget"] = 4000
        elif effort == "high":
            thinking_cfg["thinkingBudget"] = 8000
    elif model_spec.get("supports_thinking") and ("-high" in model.lower() or "thinking" in model.lower()):
        thinking_cfg = {"includeThoughts": True, "thinkingLevel": "high", "thinkingBudget": 8000}

    if thinking_cfg:
        generation_config["thinkingConfig"] = thinking_cfg
        # Ensure temperature conforms to Gemini thinking constraints (must be default/1.0)
        generation_config["temperature"] = 1.0


    req_payload: Dict[str, Any] = {
        "contents": contents,
        "systemInstruction": system_instruction,
    }
    if generation_config:
        req_payload["generationConfig"] = generation_config
    if tools_list:
        req_payload["tools"] = tools_list
    if tool_config:
        req_payload["toolConfig"] = tool_config

    return model, req_payload


def estimate_anthropic_tokens(body: Dict[str, Any]) -> int:
    """Estimates total input tokens for Anthropic /v1/messages/count_tokens."""
    total_chars = 0
    # System
    sys_val = body.get("system")
    if isinstance(sys_val, str):
        total_chars += len(sys_val)
    elif isinstance(sys_val, list):
        for b in sys_val:
            if isinstance(b, dict):
                total_chars += len(b.get("text", ""))

    # Messages
    msgs = body.get("messages", [])
    for m in msgs:
        c = m.get("content", "")
        if isinstance(c, str):
            total_chars += len(c)
        elif isinstance(c, list):
            for b in c:
                if isinstance(b, dict):
                    total_chars += len(b.get("text", ""))
                    if b.get("type") == "image":
                        total_chars += 1600  # standard ~400 tokens per image
                    elif b.get("type") == "tool_use":
                        total_chars += len(json.dumps(b.get("input", {})))
                    elif b.get("type") == "tool_result":
                        total_chars += len(str(b.get("content", "")))

    # Tools
    tools = body.get("tools", [])
    if tools:
        total_chars += len(json.dumps(tools))

    return max(1, total_chars // 4)


def format_anthropic_non_stream_response(
    message_id: str,
    model: str,
    content_blocks: List[Dict[str, Any]],
    stop_reason: str = "end_turn",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0
) -> Dict[str, Any]:
    """Generates standard Anthropic JSON response for non-streaming calls."""
    return {
        "id": message_id,
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cache_creation_input_tokens": cache_creation_tokens,
            "cache_read_input_tokens": cache_read_tokens
        }
    }


async def stream_cached_anthropic_sse(
    message_id: str,
    model: str,
    cached: Dict[str, Any],
    prompt_tokens: int = 0
) -> AsyncGenerator[str, None]:
    """Instantly streams a cached response in standard Anthropic SSE event format (~5ms TTFT)."""
    response_text = cached.get("response_text", "")
    cached_tokens = cached.get("total_tokens", prompt_tokens)

    # 1. message_start
    yield format_anthropic_sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": prompt_tokens,
                "output_tokens": 1,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": cached_tokens
            }
        }
    })

    # 2. content_block_start
    yield format_anthropic_sse_event("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""}
    })

    # 3. content_block_delta (stream in smooth token chunks)
    if response_text:
        words = response_text.split(" ")
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            yield format_anthropic_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": chunk}
            })
            if len(words) > 8:
                await asyncio.sleep(0.003)

    # 4. content_block_stop
    yield format_anthropic_sse_event("content_block_stop", {
        "type": "content_block_stop",
        "index": 0
    })

    # 5. message_delta
    output_tokens = max(1, len(response_text) // 4)
    yield format_anthropic_sse_event("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": output_tokens}
    })

    # 6. message_stop
    yield format_anthropic_sse_event("message_stop", {
        "type": "message_stop"
    })


async def stream_anthropic_sse(
    ordered_accounts: List[Dict[str, Any]],
    model: str,
    req_payload: Dict[str, Any],
    message_id: str,
    created: int,
    cache_meta: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Connects to Google Antigravity upstream with transparent mid-flight failover,
    translating live SSE chunks into strict Anthropic SSE lifecycle events.
    """
    start_t = time.time()
    prompt_tokens = max(1, len(json.dumps(req_payload)) // 4)
    completion_tokens = 0
    accumulated_content: List[str] = []

    timeout = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)
    connected_resp = None
    connected_account = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt, account in enumerate(ordered_accounts):
            account_email = account.get("email", "")
            try:
                access_token = await get_access_token(account)
                project_id = account.get("projectId", "rising-fact-p41fc")
                upstream_url = f"{ANTIGRAVITY_ENDPOINT}/v1internal:streamGenerateContent?alt=sse"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "Antigravity/2.24.0.0",
                    "Accept": "text/event-stream"
                }
                wrapped_body = {
                    "project": project_id,
                    "model": model,
                    "request": req_payload,
                    "requestType": "agent",
                    "userAgent": "antigravity",
                    "requestId": "agent-" + uuid.uuid4().hex
                }

                req = client.build_request("POST", upstream_url, headers=headers, json=wrapped_body)
                resp = await client.send(req, stream=True)

                if resp.status_code in (429, 503):
                    AccountFailoverPool.mark_rate_limited(account_email, cooldown_seconds=25)
                    logger.warning(
                        f"[MID-FLIGHT FAILOVER (ANTHROPIC)] Upstream HTTP {resp.status_code} on {account_email}. "
                        f"Rotating to next available account transparently..."
                    )
                    try:
                        event_bus.broadcast_sync({
                            "type": "ACCOUNT_FAILOVER",
                            "account": account_email,
                            "status_code": resp.status_code
                        })
                    except Exception:
                        pass
                    await resp.aclose()
                    await asyncio.sleep(0.4)
                    continue

                if resp.status_code != 200:
                    err_text = await resp.aread()
                    logger.error(f"Upstream stream error {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:300]}")
                    await resp.aclose()
                    if attempt < len(ordered_accounts) - 1:
                        continue
                    yield format_anthropic_sse_event("error", {
                        "type": "error",
                        "error": {"type": "api_error", "message": f"Upstream error: {resp.status_code}"}
                    })
                    return

                # Successfully connected to upstream
                connected_resp = resp
                connected_account = account
                break
            except Exception as e:
                logger.error(f"[MID-FLIGHT FAILOVER (ANTHROPIC)] Connection failed for {account_email}: {e}")
                if attempt == len(ordered_accounts) - 1:
                    yield format_anthropic_sse_event("error", {
                        "type": "error",
                        "error": {"type": "api_error", "message": f"Upstream connection failed: {e}"}
                    })
                    return
                continue

        if not connected_resp:
            yield format_anthropic_sse_event("error", {
                "type": "error",
                "error": {"type": "api_error", "message": "All upstream accounts exhausted or failed."}
            })
            return

        resp = connected_resp
        account_email = connected_account.get("email") if connected_account else None

        # 1. Yield message_start
        yield format_anthropic_sse_event("message_start", {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": 1,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0
                }
            }
        })

        current_block_index = -1
        in_text_block = False
        in_tool_block = False
        has_emitted_tool = False

        try:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data_str)
                    except Exception:
                        continue

                    # Parse Antigravity Candidates
                    response_obj = chunk.get("response", chunk)
                    candidates = response_obj.get("candidates", [])
                    if not candidates:
                        continue

                    cand = candidates[0]
                    content_obj = cand.get("content", {})
                    parts = content_obj.get("parts", [])

                    for part in parts:
                        # Case A: Regular text output
                        if "text" in part:
                            txt = part["text"]
                            if txt:
                                if not in_text_block:
                                    if in_tool_block:
                                        yield format_anthropic_sse_event("content_block_stop", {"type": "content_block_stop", "index": current_block_index})
                                        in_tool_block = False
                                    current_block_index += 1
                                    yield format_anthropic_sse_event("content_block_start", {
                                        "type": "content_block_start",
                                        "index": current_block_index,
                                        "content_block": {"type": "text", "text": ""}
                                    })
                                    in_text_block = True

                                yield format_anthropic_sse_event("content_block_delta", {
                                    "type": "content_block_delta",
                                    "index": current_block_index,
                                    "delta": {"type": "text_delta", "text": txt}
                                })
                                accumulated_content.append(txt)
                                completion_tokens += max(1, len(txt) // 4)

                        # Case B: Tool / Function Call
                        elif "functionCall" in part:
                            fn = part["functionCall"]
                            fn_name = fn.get("name", "tool")
                            fn_args = fn.get("args", {})
                            call_id = fn.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"
                            has_emitted_tool = True

                            if in_text_block:
                                yield format_anthropic_sse_event("content_block_stop", {"type": "content_block_stop", "index": current_block_index})
                                in_text_block = False

                            current_block_index += 1
                            in_tool_block = True

                            yield format_anthropic_sse_event("content_block_start", {
                                "type": "content_block_start",
                                "index": current_block_index,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": fn_name,
                                    "input": {}
                                }
                            })

                            args_json = json.dumps(fn_args) if isinstance(fn_args, dict) else str(fn_args)
                            yield format_anthropic_sse_event("content_block_delta", {
                                "type": "content_block_delta",
                                "index": current_block_index,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": args_json
                                }
                            })
                            yield format_anthropic_sse_event("content_block_stop", {
                                "type": "content_block_stop",
                                "index": current_block_index
                            })
                            in_tool_block = False
                            completion_tokens += max(1, len(args_json) // 4)

            # Close any open block
            if in_text_block or in_tool_block:
                yield format_anthropic_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": current_block_index
                })

            # Record telemetry & cache
            latency_ms = round((time.time() - start_t) * 1000, 1)
            telemetry.record_usage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=0,
                latency_ms=latency_ms
            )

            # Save in compiled binary DB cache if eligible
            full_text = "".join(accumulated_content)
            if cache_meta and cache_meta.get("eligible") and full_text and not has_emitted_tool:
                try:
                    emb_bytes = None
                    last_q = cache_meta.get("last_user_query")
                    if last_q:
                        from ..cache.semantic import SemanticVectorEngine
                        q_vec = SemanticVectorEngine.embed_text(last_q)
                        if q_vec is not None:
                            emb_bytes = SemanticVectorEngine.vector_to_blob(q_vec)

                    db.store_cached_response(
                        cache_key=cache_meta.get("cache_key") or cache_meta.get("key"),
                        prompt_hash=cache_meta.get("prompt_hash") or cache_meta.get("hash"),
                        prompt_preview=cache_meta.get("preview") or cache_meta.get("prompt_preview"),
                        response_text=full_text,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        reasoning_tokens=0,
                        embedding=emb_bytes,
                        tools_signature=cache_meta.get("tools_sig")
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache Anthropic response: {e}")

            # Record request hit in ledger
            try:
                quota_snap = QuotaMonitor.get_cached_quotas(account_email) if account_email else None
                db.record_request_hit(
                    request_id=message_id,
                    timestamp=created,
                    account_email=account_email,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=0,
                    latency_ms=latency_ms,
                    status_code=200,
                    stream=1,
                    quota_snapshot=quota_snap,
                    cache_hit=0,
                    tokens_saved=0
                )
            except Exception as e:
                logger.error(f"Failed to record Anthropic request hit: {e}")

            # Live broadcast to WebSocket clients
            try:
                event_bus.broadcast_sync({
                    "type": "REQUEST_LOGGED",
                    "request_id": message_id,
                    "model": model,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "cache_hit": False,
                    "tokens_saved": 0
                })
            except Exception:
                pass

            # Yield message_delta
            stop_reason = "tool_use" if has_emitted_tool else "end_turn"
            yield format_anthropic_sse_event("message_delta", {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": max(1, completion_tokens)}
            })

            # Yield message_stop
            yield format_anthropic_sse_event("message_stop", {
                "type": "message_stop"
            })

        finally:
            await resp.aclose()
