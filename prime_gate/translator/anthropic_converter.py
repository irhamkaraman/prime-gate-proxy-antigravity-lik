import re
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
from .response_converter import extract_text_tool_calls, normalize_tool_call
from .thought_cache import thought_sig_cache
from ..quota.monitor import QuotaMonitor
from ..client_pool import get_shared_client

logger = logging.getLogger("prime_gate.translator.anthropic_converter")

ANTIGRAVITY_ENDPOINT = "https://daily-cloudcode-pa.sandbox.googleapis.com"


def parse_text_tool_call(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Detects and parses raw text tool calls emitted by Gemini internal checkpoints,
    e.g. 'call:default_api:Glob{pattern:*.ps1}' or 'call:Edit{...}'.
    Returns (tool_name, args_dict) if matched, otherwise None.
    """
    clean_text = text.strip()
    if not clean_text.startswith("call:"):
        return None

    match = re.match(r"^call:(?:default_api:)?([a-zA-Z0-9_-]+)\s*(\{[\s\S]*\})$", clean_text)
    if not match:
        return None

    fn_name = match.group(1)
    raw_body = match.group(2).strip()

    # 1. Try standard JSON parse
    try:
        args = json.loads(raw_body)
        if isinstance(args, dict):
            return fn_name, args
    except Exception:
        pass

    # 2. Relaxed key:value parser for Google internal syntax (e.g. {pattern:*.ps1})
    inner = raw_body[1:-1].strip()
    args: Dict[str, Any] = {}
    if inner:
        parts = re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", inner)
        for p in parts:
            if ":" in p:
                k, v = p.split(":", 1)
                k = k.strip().strip("'\"")
                v = v.strip().strip("'\"")
                if v.lower() == "true":
                    args[k] = True
                elif v.lower() == "false":
                    args[k] = False
                elif v.isdigit():
                    args[k] = int(v)
                else:
                    args[k] = v
    return fn_name, args


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

                    part_entry = {
                        "functionCall": {
                            "name": fn_name,
                            "args": raw_input,
                            "id": call_id
                        }
                    }
                    sig = (
                        block.get("thoughtSignature")
                        or block.get("thought_signature")
                        or thought_sig_cache.get(call_id)
                        or thought_sig_cache.get(fn_name)
                    )
                    if sig and sig != "skip_thought_signature_validator":
                        part_entry["thoughtSignature"] = sig
                    parts.append(part_entry)

                elif b_type == "tool_result":
                    call_id = block.get("tool_use_id", "")
                    fn_name = block.get("name") or tool_call_map.get(call_id, "unknown_tool")
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

    # Antigravity/Gemini protocol invariants:
    # 1. First turn must be 'user'
    if contents and contents[0].get("role") == "model":
        contents.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})

    # 2. Last turn cannot be 'model' (Anthropic prefill messages ending with assistant turn
    #    trigger Google Antigravity 400 'Requests ending with a model turn are not supported')
    if contents and contents[-1].get("role") == "model":
        contents.append({"role": "user", "parts": [{"text": "Continue"}]})

    # System instruction handling
    # Google Antigravity Sandbox Gateway imposes an undocumented character cap (~1,500 chars)
    # on dedicated `systemInstruction` objects, throwing false-positive 429 RESOURCE_EXHAUSTED.
    # If the system prompt is large (e.g. Claude Code CLI harness prompts > 1,200 chars),
    # we inject it directly into the first user turn in `contents`, where Antigravity allows 1M+ tokens.
    # Meanwhile, we maintain a concise (<500 chars) persistent agentic coding directive in `systemInstruction`
    # so Gemini's attention heads consistently prioritize invoking tools (Edit/Write) rather than printing code.
    agentic_rule = (
        "You are an expert autonomous software engineer. "
        "When tools (such as Edit, Write, Bash) are available and the user requests code changes, "
        "fixes, refactoring, or adding comments: ALWAYS invoke the Edit or Write tool to apply "
        "the changes directly to the file(s) on disk. DO NOT merely output markdown code blocks "
        "in chat when file modification is requested; directly execute the tool edits."
    )

    if system_texts:
        full_system_str = "\n\n".join([t for t in system_texts if t])
    else:
        full_system_str = SYSTEM_INSTRUCTION

    if len(full_system_str) > 1200:
        instruction_prefix = f"[System Instruction]\n{full_system_str}\n\n"
        if contents and contents[0].get("role") == "user":
            if contents[0].get("parts") and "text" in contents[0]["parts"][0]:
                contents[0]["parts"][0]["text"] = instruction_prefix + contents[0]["parts"][0]["text"]
            else:
                contents[0]["parts"].insert(0, {"text": instruction_prefix.strip()})
        else:
            contents.insert(0, {"role": "user", "parts": [{"text": instruction_prefix.strip()}]})

        system_instruction = {
            "role": "user",
            "parts": [{"text": agentic_rule}]
        }
    else:
        combined_sys = f"{full_system_str}\n\n{agentic_rule}" if len(full_system_str) + len(agentic_rule) < 1200 else full_system_str
        system_instruction = {
            "role": "user",
            "parts": [{"text": combined_sys}]
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
    elif tools_list:
        tool_config = {"functionCallingConfig": {"mode": "AUTO"}}

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

        # Ensure maxOutputTokens has sufficient headroom for both thoughts and answer tokens
        budget = thinking_cfg.get("thinkingBudget")
        current_max = generation_config.get("maxOutputTokens")
        if budget and isinstance(budget, int) and budget > 0:
            if current_max is None or current_max <= budget:
                generation_config["maxOutputTokens"] = budget + 8192
        elif current_max is None:
            generation_config["maxOutputTokens"] = 16384

    # Default safe maximum output token cap to prevent premature truncation
    if "maxOutputTokens" not in generation_config:
        generation_config["maxOutputTokens"] = 16384


    req_payload: Dict[str, Any] = {
        "contents": contents,
    }
    if system_instruction:
        req_payload["systemInstruction"] = system_instruction
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
    declared_tools: Optional[List[Dict[str, Any]]] = None,
    cache_meta: Optional[Dict[str, Any]] = None,
    acquired_email: Optional[str] = None,
    key_id: Optional[int] = None
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
    current_held_email = acquired_email

    client = get_shared_client()
    # Immediately flush HTTP 200 OK headers to prevent client connection/read timeout
    yield ": connected\n\n"
    try:
        max_attempts = max(len(ordered_accounts) * 2, 4)
        for attempt in range(max_attempts):
            if attempt < len(ordered_accounts):
                account = ordered_accounts[attempt]
            else:
                try:
                    q_cache = QuotaMonitor.get_cached_quotas()
                except Exception:
                    q_cache = None
                refreshed = AccountFailoverPool.get_ordered_accounts(
                    accounts=ordered_accounts,
                    quota_cache=q_cache
                )
                account = refreshed[attempt % len(refreshed)]

            account_email = account.get("email", "")
            if current_held_email != account_email:
                if current_held_email:
                    AccountFailoverPool.release(current_held_email)
                AccountFailoverPool.acquire(account_email)
                current_held_email = account_email

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
                send_task = asyncio.create_task(client.send(req, stream=True))
                while not send_task.done():
                    try:
                        resp = await asyncio.wait_for(asyncio.shield(send_task), timeout=5.0)
                        break
                    except asyncio.TimeoutError:
                        yield ": ping\n\n" 

                if resp.status_code in (429, 503):
                    err_text = await resp.aread()
                    AccountFailoverPool.mark_rate_limited(account_email, cooldown_seconds=6)
                    logger.warning(
                        f"[MID-FLIGHT FAILOVER (ANTHROPIC)] Upstream HTTP {resp.status_code} on {account_email}: "
                        f"{err_text.decode('utf-8', errors='ignore')[:300]}. Rotating to next available account transparently..."
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
                    if attempt == max_attempts - 1:
                        await asyncio.sleep(1.2)
                    else:
                        await asyncio.sleep(0.4)
                    continue

                if resp.status_code != 200:
                    err_text = await resp.aread()
                    logger.error(f"Upstream stream error {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:300]}")
                    await resp.aclose()
                    if attempt < max_attempts - 1:
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
                if attempt == max_attempts - 1:
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
        in_call_block = False
        call_buffer = ""
        text_buffer = ""

        def emit_text(t: str):
            nonlocal in_text_block, in_tool_block, current_block_index, completion_tokens
            if not t:
                return []
            events = []
            if in_tool_block:
                events.append(format_anthropic_sse_event("content_block_stop", {"type": "content_block_stop", "index": current_block_index}))
                in_tool_block = False
            if not in_text_block:
                current_block_index += 1
                events.append(format_anthropic_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": current_block_index,
                    "content_block": {"type": "text", "text": ""}
                }))
                in_text_block = True
            events.append(format_anthropic_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": current_block_index,
                "delta": {"type": "text_delta", "text": t}
            }))
            accumulated_content.append(t)
            completion_tokens += max(1, len(t) // 4)
            return events

        def emit_tool(name: str, args: Any, tool_id: Optional[str] = None):
            nonlocal in_text_block, in_tool_block, current_block_index, has_emitted_tool, completion_tokens
            events = []
            call_id = tool_id or f"toolu_{uuid.uuid4().hex[:12]}"
            has_emitted_tool = True
            if in_text_block:
                events.append(format_anthropic_sse_event("content_block_stop", {"type": "content_block_stop", "index": current_block_index}))
                in_text_block = False
            if in_tool_block:
                events.append(format_anthropic_sse_event("content_block_stop", {"type": "content_block_stop", "index": current_block_index}))
                in_tool_block = False
            current_block_index += 1
            events.append(format_anthropic_sse_event("content_block_start", {
                "type": "content_block_start",
                "index": current_block_index,
                "content_block": {
                    "type": "tool_use",
                    "id": call_id,
                    "name": name,
                    "input": {}
                }
            }))
            args_json = json.dumps(args) if isinstance(args, dict) else str(args)
            events.append(format_anthropic_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": current_block_index,
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": args_json
                }
            }))
            events.append(format_anthropic_sse_event("content_block_stop", {
                "type": "content_block_stop",
                "index": current_block_index
            }))
            completion_tokens += max(1, len(args_json) // 4)
            return events

        def is_braces_balanced(s: str) -> bool:
            if "{" not in s:
                return False
            depth = 0
            in_str = False
            quote_char = ''
            escape = False
            for ch in s:
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
                        return True
            return False

        try:
            aiter = resp.aiter_lines().__aiter__()
            while True:
                try:
                    line = await asyncio.wait_for(aiter.__anext__(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Upstream Antigravity is processing prompt/thinking; emit SSE comment heartbeat
                    yield ": ping\n\n"
                    continue
                except StopAsyncIteration:
                    break

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
                    cand_sig = None
                    for p in parts:
                        s = p.get("thoughtSignature") or p.get("thought_signature")
                        if s and s != "skip_thought_signature_validator":
                            cand_sig = s
                            break

                    for part in parts:
                        # Case A: Regular text output or text-based tool call interceptor
                        if "text" in part:
                            txt = part["text"]
                            if not txt:
                                continue

                            if in_call_block:
                                call_buffer += txt
                                if is_braces_balanced(call_buffer):
                                    cleaned, tcs = extract_text_tool_calls(call_buffer, declared_tools)
                                    if tcs:
                                        for tc in tcs:
                                            fn = tc["function"]
                                            fn_name = fn["name"]
                                            fn_args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                                            tc_id = tc.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"
                                            for ev in emit_tool(fn_name, fn_args, tc_id):
                                                yield ev
                                        in_call_block = False
                                        call_buffer = ""
                                        if cleaned:
                                            text_buffer += cleaned
                                    else:
                                        for ev in emit_text(call_buffer):
                                            yield ev
                                        in_call_block = False
                                        call_buffer = ""
                            else:
                                text_buffer += txt
                                if "call:" in text_buffer:
                                    idx = text_buffer.find("call:")
                                    before_call = text_buffer[:idx]
                                    call_tail = text_buffer[idx:]
                                    text_buffer = ""
                                    if before_call:
                                        for ev in emit_text(before_call):
                                            yield ev
                                    in_call_block = True
                                    call_buffer = call_tail
                                    if is_braces_balanced(call_buffer):
                                        cleaned, tcs = extract_text_tool_calls(call_buffer, declared_tools)
                                        if tcs:
                                            for tc in tcs:
                                                fn = tc["function"]
                                                fn_name = fn["name"]
                                                fn_args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                                                tc_id = tc.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"
                                                for ev in emit_tool(fn_name, fn_args, tc_id):
                                                    yield ev
                                            in_call_block = False
                                            call_buffer = ""
                                            if cleaned:
                                                text_buffer += cleaned
                                        else:
                                            for ev in emit_text(call_buffer):
                                                yield ev
                                            in_call_block = False
                                            call_buffer = ""
                                else:
                                    prefix_len = 0
                                    for pfx in ("call", "cal", "ca", "c"):
                                        if text_buffer.endswith(pfx):
                                            prefix_len = len(pfx)
                                            break
                                    to_yield = text_buffer[:-prefix_len] if prefix_len > 0 else text_buffer
                                    text_buffer = text_buffer[-prefix_len:] if prefix_len > 0 else ""
                                    if to_yield:
                                        for ev in emit_text(to_yield):
                                            yield ev

                        # Case B: Tool / Function Call
                        elif "functionCall" in part:
                            fn = part["functionCall"]
                            raw_name = fn.get("name", "tool")
                            raw_args = fn.get("args", {})
                            fn_name, fn_args = normalize_tool_call(raw_name, raw_args, declared_tools)
                            call_id = fn.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"
                            sig = part.get("thoughtSignature") or part.get("thought_signature") or cand_sig
                            if sig and sig != "skip_thought_signature_validator":
                                thought_sig_cache.store(call_id, sig)
                                thought_sig_cache.store(fn_name, sig)
                            for ev in emit_tool(fn_name, fn_args, call_id):
                                yield ev

            # Flush any remaining buffers
            if in_call_block and call_buffer:
                cleaned, tcs = extract_text_tool_calls(call_buffer, declared_tools)
                if tcs:
                    for tc in tcs:
                        fn = tc["function"]
                        fn_name = fn["name"]
                        fn_args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                        tc_id = tc.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"
                        for ev in emit_tool(fn_name, fn_args, tc_id):
                            yield ev
                else:
                    for ev in emit_text(call_buffer):
                        yield ev
                in_call_block = False
                call_buffer = ""

            if text_buffer:
                for ev in emit_text(text_buffer):
                    yield ev
                text_buffer = ""

            # Close any open block
            if in_text_block or in_tool_block:
                yield format_anthropic_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": current_block_index
                })
                in_text_block = False
                in_tool_block = False

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
                        q_vec = SemanticVectorEngine.embed_passage(last_q)
                        if q_vec is not None:
                            emb_bytes = SemanticVectorEngine.vector_to_blob(q_vec)

                    from ..cache.semantic import SemanticVectorEngine
                    active_dim = SemanticVectorEngine.get_embedding_dimension()
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
                        tools_signature=cache_meta.get("tools_sig"),
                        scope=cache_meta.get("scope", "default"),
                        context_hash=cache_meta.get("context_hash", ""),
                        ttl_seconds=cache_meta.get("ttl", 86400),
                        embedding_model=cache_meta.get("embedding_model"),
                        embedding_dim=cache_meta.get("embedding_dim", active_dim)
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
                    tokens_saved=0,
                    key_id=key_id
                )
                if key_id:
                    db.record_api_key_tokens(
                        key_id=key_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        model=model
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
    finally:
        if current_held_email:
            AccountFailoverPool.release(current_held_email)
            current_held_email = None

