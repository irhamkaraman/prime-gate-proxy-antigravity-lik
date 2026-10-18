import json
import logging
from typing import Dict, Any, Tuple, List, Optional
from ..config import SYSTEM_INSTRUCTION
from ..db import db
from .schema_cleaner import clean_schema_for_antigravity

logger = logging.getLogger("prime_gate.translator.request_converter")

def get_dynamic_models(account_email: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve live model specifications directly from compiled binary database.
    Prioritizes models registered for account_email, falling back to models:latest,
    and finally in-memory QuotaMonitor cache.
    """
    try:
        if account_email:
            record = db.get(f"models:{account_email}")
            if record and record.get("models"):
                return record["models"]

        latest = db.get("models:latest")
        if latest and latest.get("models"):
            return latest["models"]
    except Exception as e:
        logger.warning(f"Error querying binary DB for models: {e}")

    try:
        from ..quota.monitor import QuotaMonitor
        return QuotaMonitor.get_available_models(None)
    except Exception:
        return []

def resolve_model_info(raw_model: str, account_email: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    Dynamically resolve client-requested model identifiers against the binary DB model catalog.
    Eliminates all hardcoded model mappings, ensuring forward compatibility with future models
    and multi-tier model availability (Trial vs Paid).
    """
    if not raw_model:
        m = ""
    else:
        m = raw_model.strip()
        # Strip client namespace prefix (e.g. "primegate/", "google/", "antigravity/", "anthropic/", "openai/")
        if "/" in m:
            m = m.split("/", 1)[1]

    models_catalog = get_dynamic_models(account_email)
    id_map = {m_spec["id"].lower(): m_spec for m_spec in models_catalog}

    def _return_spec(spec: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # If model is an alias or has an underlying upstream variant (e.g. gemini-3.8-flash -> gemini-3.8-flash-high)
        target = spec.get("upstream_model")
        if not target and not spec["id"].endswith(("-high", "-medium", "-low", "-tiered", "-lite")):
            # Check if upstream tiered variant exists in catalog
            for suf in ["-high", "-medium"]:
                cand = spec["id"] + suf
                if cand.lower() in id_map:
                    target = cand
                    break
        return target or spec["id"], spec

    # If empty model requested, pick the top recommended or first model from catalog
    if not m:
        for spec in models_catalog:
            if spec.get("recommended"):
                return _return_spec(spec)
        if models_catalog:
            return _return_spec(models_catalog[0])
        return "claude-sonnet-4-6", {"id": "claude-sonnet-4-6", "upstream_provider": "Anthropic", "supports_thinking": True}

    m_lower = m.lower()

    # 1. Exact canonical ID match (case-insensitive)
    if m_lower in id_map:
        return _return_spec(id_map[m_lower])

    # 2. Display Name match (case-insensitive)
    for spec in models_catalog:
        name = str(spec.get("name", "")).lower()
        if name and (m_lower == name or m_lower in name):
            return _return_spec(spec)

    # 3. Dynamic Family / Generic Alias Resolution based on DB state:
    is_generic_sonnet = m_lower in [
        "sonnet", "claude-sonnet", "claude-3-7-sonnet", "claude-3.7-sonnet",
        "claude-3-5-sonnet", "claude-3.5-sonnet", "claude-3-5-sonnet-20241022",
        "claude-3-7-sonnet-20250219", "claude-3-sonnet", "claude-sonnet-4-6"
    ]
    is_generic_opus = m_lower in [
        "opus", "claude-opus", "claude-3-opus", "claude-3.5-opus",
        "claude-3-opus-20240229", "claude-opus-4-6-thinking"
    ]
    is_generic_haiku = m_lower in [
        "haiku", "claude-haiku", "claude-3-5-haiku", "claude-3.5-haiku",
        "claude-3-5-haiku-20241022", "claude-3-haiku"
    ]
    is_generic_flash = m_lower in [
        "flash", "gemini-flash", "google-flash", "gemini-3-flash",
        "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3"
    ]
    is_generic_oss = m_lower in ["oss", "gpt-oss", "gpt-oss-120b"]
    is_legacy_gemini = m_lower.startswith("gemini-2.") or m_lower.startswith("gemini-2-") or m_lower in ["gemini-2", "gemini-2.0", "gemini-2.5"]

    if is_generic_opus:
        for spec in models_catalog:
            if "opus" in spec["id"].lower():
                return _return_spec(spec)
    elif is_generic_sonnet:
        for spec in models_catalog:
            if "sonnet" in spec["id"].lower():
                return _return_spec(spec)
    elif is_generic_haiku:
        for spec in models_catalog:
            if "flash" in spec["id"].lower() and spec.get("recommended"):
                return _return_spec(spec)
        for spec in models_catalog:
            if "flash" in spec["id"].lower():
                return _return_spec(spec)
    elif is_generic_flash:
        for spec in models_catalog:
            if "3.8-flash" in spec["id"].lower() and spec.get("recommended"):
                return _return_spec(spec)
        for spec in models_catalog:
            if "flash" in spec["id"].lower() and spec.get("recommended"):
                return _return_spec(spec)
        for spec in models_catalog:
            if "flash" in spec["id"].lower():
                return _return_spec(spec)
    elif m_lower in ["flash-high", "gemini-flash-high"]:
        for spec in models_catalog:
            if "flash" in spec["id"].lower() and "-high" in spec["id"].lower():
                return _return_spec(spec)
    elif m_lower in ["flash-medium", "gemini-flash-medium"]:
        for spec in models_catalog:
            if "flash" in spec["id"].lower() and "-medium" in spec["id"].lower():
                return _return_spec(spec)
    elif m_lower in ["flash-low", "gemini-flash-low"]:
        for spec in models_catalog:
            if "flash" in spec["id"].lower() and "-low" in spec["id"].lower():
                return _return_spec(spec)
    elif is_generic_oss:
        for spec in models_catalog:
            if "oss" in spec["id"].lower():
                return _return_spec(spec)
    elif is_legacy_gemini:
        # Safe fallback for obsolete/deprecated legacy models to avoid 400/503 capacity errors
        for spec in models_catalog:
            if "flash" in spec["id"].lower() and spec.get("recommended"):
                return _return_spec(spec)
        for spec in models_catalog:
            if "gemini" in spec["id"].lower():
                return _return_spec(spec)

    # 4. Forward compatibility: Unknown / brand new future model requested
    prov = "Google"
    if "claude" in m_lower:
        prov = "Anthropic"
    elif "gpt" in m_lower:
        prov = "OpenAI"

    has_thinking = bool("thinking" in m_lower or "opus" in m_lower or "-high" in m_lower or "flash" in m_lower)
    synthetic_spec = {
        "id": m,
        "name": m,
        "upstream_provider": prov,
        "supports_thinking": has_thinking,
        "thinking_budget": -1 if "-high" in m_lower else 0,
        "thinking_level": "high" if "-high" in m_lower else "medium"
    }
    return m, synthetic_spec

def resolve_model_name(raw_model: str, account_email: Optional[str] = None) -> str:
    """Normalize client model names to Antigravity internal identifiers (backward compatible)."""
    model_id, _ = resolve_model_info(raw_model, account_email)
    return model_id

def transform_openai_to_antigravity(
    body: Dict[str, Any],
    account: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """Transform standard OpenAI Chat Completion request dictionary into Antigravity internal format."""
    account_email = account.get("email") if isinstance(account, dict) else None
    model, model_spec = resolve_model_info(body.get("model", ""), account_email=account_email)

    upstream_provider = str(model_spec.get("upstream_provider", "")).lower()
    is_claude = upstream_provider == "anthropic" or "claude" in model.lower()
    supports_thinking = bool(model_spec.get("supports_thinking", False))

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

                        fn_payload = {
                            "name": fn_name,
                            "args": fn_args if isinstance(fn_args, dict) else {}
                        }
                        if call_id:
                            fn_payload["id"] = call_id

                        parts.append({
                            "functionCall": fn_payload,
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
            elif isinstance(out_val, list):
                # Extract text if it's OpenAI content parts list
                text_parts = []
                for p in out_val:
                    if isinstance(p, dict) and p.get("type") == "text" and p.get("text"):
                        text_parts.append(p["text"])
                    elif isinstance(p, str):
                        text_parts.append(p)
                if text_parts:
                    response_dict = {"output": "\n".join(text_parts)}
                else:
                    response_dict = {"output": out_val}
            else:
                response_dict = {"output": str(out_val) if out_val is not None else ""}

            fn_resp_obj: Dict[str, Any] = {
                "name": fn_name,
                "response": response_dict
            }
            if call_id:
                fn_resp_obj["id"] = call_id

            fn_part = {
                "functionResponse": fn_resp_obj
            }

            # If preceding turn was already user containing functionResponse, merge parts for parallel tool calls
            if contents and contents[-1].get("role") == "user" and any("functionResponse" in p for p in contents[-1].get("parts", [])):
                contents[-1]["parts"].append(fn_part)
            else:
                contents.append({
                    "role": "user",
                    "parts": [fn_part]
                })

    # Antigravity/Gemini protocol invariants:
    if contents and contents[0].get("role") == "model":
        contents.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})
    if contents and contents[-1].get("role") == "model":
        contents.append({"role": "user", "parts": [{"text": "Continue"}]})

    # System instruction: prioritize client's own system prompt over generic fallback.
    # If system prompt exceeds 1,200 chars, merge into the first user turn in contents
    # to avoid Google Antigravity internal gateway 429 RESOURCE_EXHAUSTED.
    agentic_rule = (
        "You are an expert autonomous software engineer. "
        "When tools (such as Edit, Write, Bash) are available and the user requests code changes, "
        "fixes, refactoring, or adding comments: ALWAYS invoke the Edit or Write tool to apply "
        "the changes directly to the file(s) on disk. DO NOT merely output markdown code blocks "
        "in chat when file modification is requested; directly execute the tool edits."
    )

    if system_texts:
        full_system_str = "\n\n".join([p for p in system_texts if p])
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
            # Deterministic sorting by function name ensures consistent upstream byte prefix caching
            declarations.sort(key=lambda d: d.get("name", ""))
            tools.append({"functionDeclarations": declarations})

    # Generation config
    generation_config: Dict[str, Any] = {}
    if "temperature" in body and body["temperature"] is not None:
        generation_config["temperature"] = body["temperature"]
    if "top_p" in body and body["top_p"] is not None:
        generation_config["topP"] = body["top_p"]

    max_tok = body.get("max_completion_tokens") or body.get("max_tokens")
    if max_tok is not None:
        generation_config["maxOutputTokens"] = max_tok

    stop = body.get("stop")
    if stop:
        if isinstance(stop, str):
            generation_config["stopSequences"] = [stop]
        elif isinstance(stop, list):
            generation_config["stopSequences"] = [s for s in stop if isinstance(s, str)]

    # OpenAI-compatible reasoning / thinking parameters
    reasoning_effort = str(body.get("reasoning_effort", "")).lower().strip()
    thinking_param = body.get("thinking")
    explicit_budget = None
    if isinstance(thinking_param, dict):
        explicit_budget = thinking_param.get("budget_tokens") or thinking_param.get("budget")

    # Dynamic reasoning & thinking configuration based on model specs from DB
    if is_claude:
        # Claude Extended Thinking should ONLY be enabled when explicitly requested by user/client
        # or model has 'thinking' in its name (e.g. claude-opus-4-6-thinking)
        claude_thinking_requested = (
            explicit_budget is not None
            or reasoning_effort in ["low", "medium", "high"]
            or "thinking" in model.lower()
        )
        if claude_thinking_requested and supports_thinking:
            claude_budget = explicit_budget or 8192
            if reasoning_effort == "low":
                claude_budget = 2048
            elif reasoning_effort == "high":
                claude_budget = 16384
            elif model_spec.get("thinking_budget") and model_spec["thinking_budget"] > 0:
                claude_budget = model_spec["thinking_budget"]

            # Anthropic constraint: max_output_tokens must be greater than thinking_budget
            current_max = generation_config.get("maxOutputTokens")
            if current_max is not None and current_max <= claude_budget:
                generation_config["maxOutputTokens"] = claude_budget + 1024

            generation_config["thinkingConfig"] = {
                "include_thoughts": True,
                "thinking_budget": claude_budget
            }
    elif supports_thinking or reasoning_effort in ["low", "medium", "high"] or explicit_budget is not None or "thinking" in model.lower():
            gemini_level = "medium"
            if reasoning_effort in ["low", "medium", "high"]:
                gemini_level = reasoning_effort
            elif model_spec.get("thinking_level") in ["low", "medium", "high"]:
                gemini_level = model_spec["thinking_level"]
            elif "-high" in model.lower():
                gemini_level = "high"
            elif "-low" in model.lower():
                gemini_level = "low"

            thinking_cfg: Dict[str, Any] = {
                "includeThoughts": True,
                "thinkingLevel": gemini_level
            }
            if explicit_budget is not None and isinstance(explicit_budget, int):
                thinking_cfg["thinkingBudget"] = explicit_budget
            elif model_spec.get("thinking_budget") and model_spec["thinking_budget"] > 0:
                thinking_cfg["thinkingBudget"] = model_spec["thinking_budget"]

            generation_config["thinkingConfig"] = thinking_cfg

    req_payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": generation_config
    }
    if system_instruction:
        req_payload["systemInstruction"] = system_instruction

    if tools:
        req_payload["tools"] = tools

        # Map tool_choice to Antigravity functionCallingConfig
        tool_choice = body.get("tool_choice")
        mode = "AUTO"
        allowed_functions = None

        if tool_choice:
            if isinstance(tool_choice, str):
                tc_lower = tool_choice.lower()
                if tc_lower in ("auto", "default"):
                    mode = "VALIDATED" if is_claude else "AUTO"
                elif tc_lower in ("required", "any"):
                    mode = "ANY"
                elif tc_lower == "none":
                    mode = "NONE"
            elif isinstance(tool_choice, dict):
                fn_name = tool_choice.get("function", {}).get("name")
                if fn_name:
                    mode = "ANY"
                    allowed_functions = [fn_name]
        else:
            mode = "VALIDATED" if is_claude else "AUTO"

        fcc: Dict[str, Any] = {"mode": mode}
        if allowed_functions:
            fcc["allowedFunctionNames"] = allowed_functions

        req_payload["toolConfig"] = {
            "functionCallingConfig": fcc
        }

    return model, req_payload
