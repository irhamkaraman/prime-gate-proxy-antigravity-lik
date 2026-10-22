import time
import json
import threading
from collections import defaultdict, deque
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from ..db import db


class KeyRateLimiter:
    """
    Sliding-window rate limiter and policy enforcement engine for Client Gateway API Keys:
    - Requests Per Minute (RPM) sliding window enforcement.
    - Tokens Per Day (TPD) 24-hour sliding usage window enforcement.
    - Quota credits lifetime threshold enforcement.
    - Allowed models whitelist verification.
    - Protocol-specific error body formatting (OpenAI vs. Anthropic) with Retry-After headers.
    """

    _rpm_timestamps: Dict[int, deque] = defaultdict(deque)
    _lock = threading.Lock()

    @classmethod
    def reset_in_memory_state(cls):
        """Clears in-memory sliding windows (used for test teardown)."""
        with cls._lock:
            cls._rpm_timestamps.clear()

    @classmethod
    def _build_429_error(cls, path: str, message: str, retry_after: int) -> HTTPException:
        """Constructs a protocol-compliant 429 Too Many Requests exception."""
        is_anthropic = "/messages" in path
        if is_anthropic:
            detail = {
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": message
                }
            }
        else:
            detail = {
                "error": {
                    "message": message,
                    "type": "rate_limit_error",
                    "param": None,
                    "code": "rate_limit_exceeded"
                }
            }

        return HTTPException(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(max(1, retry_after))}
        )

    @classmethod
    def check_limits(cls, key_record: Dict[str, Any], path: str) -> Optional[HTTPException]:
        """
        Evaluates RPM, TPD, and Quota for the given Client Gateway API Key.
        Returns HTTPException(429) if a limit is exceeded, or None if compliant.
        """
        key_id = key_record.get("id")
        key_name = key_record.get("name", "client")
        rpm_limit = int(key_record.get("rate_limit_rpm", 0) or 0)
        tpd_limit = int(key_record.get("rate_limit_tpd", 0) or 0)
        quota_credits = float(key_record.get("quota_credits", 0.0) or 0.0)
        now = time.time()

        # 1. RPM Sliding Window Check (Requests per 60 seconds)
        if rpm_limit > 0 and key_id is not None:
            with cls._lock:
                dq = cls._rpm_timestamps[key_id]
                cutoff = now - 60.0
                while dq and dq[0] < cutoff:
                    dq.popleft()

                if len(dq) >= rpm_limit:
                    oldest_ts = dq[0]
                    retry_after = max(1, int(60.0 - (now - oldest_ts)))
                    msg = (
                        f"Rate limit exceeded for API key '{key_name}': "
                        f"maximum {rpm_limit} requests per minute reached. Please retry after {retry_after}s."
                    )
                    return cls._build_429_error(path, msg, retry_after)

                # Record current request in sliding window
                dq.append(now)

        # 2. TPD Sliding Window Check (LLM Inference Tokens per 24 Hours)
        if tpd_limit > 0 and key_id is not None:
            used_tokens_today = db.get_api_key_usage_today(key_id)
            if used_tokens_today >= tpd_limit:
                msg = (
                    f"Daily token limit reached for API key '{key_name}': "
                    f"used {used_tokens_today} tokens out of {tpd_limit} allowed per day."
                )
                return cls._build_429_error(path, msg, retry_after=3600)

        # 3. Lifetime Quota Credits Check
        if quota_credits > 0.0 and key_id is not None:
            lifetime_tokens = db.get_api_key_lifetime_usage(key_id)
            if lifetime_tokens >= quota_credits:
                msg = (
                    f"Total quota exceeded for API key '{key_name}': "
                    f"consumed {lifetime_tokens} tokens (quota: {int(quota_credits)})."
                )
                return cls._build_429_error(path, msg, retry_after=86400)

        return None

    @classmethod
    def check_model_allowed(cls, key_record: Dict[str, Any], requested_model: str, path: str) -> Optional[HTTPException]:
        """
        Validates whether requested_model is permitted for this Client Gateway API Key.
        Returns HTTPException(403) if disallowed, or None if authorized.
        """
        allowed_raw = key_record.get("allowed_models", "[]")
        allowed: List[str] = []
        if isinstance(allowed_raw, list):
            allowed = allowed_raw
        elif isinstance(allowed_raw, str):
            try:
                parsed = json.loads(allowed_raw)
                if isinstance(parsed, list):
                    allowed = parsed
            except Exception:
                allowed = []

        # Empty list or wildcard '*' / 'all' implies all models are permitted
        if not allowed or "*" in allowed or "all" in allowed:
            return None

        # Direct match or case-insensitive match
        req_clean = (requested_model or "").strip()
        allowed_normalized = [m.strip().lower() for m in allowed]
        if req_clean.lower() not in allowed_normalized:
            is_anthropic = "/messages" in path
            key_name = key_record.get("name", "client")
            if is_anthropic:
                detail = {
                    "type": "error",
                    "error": {
                        "type": "permission_error",
                        "message": (
                            f"Model '{requested_model}' is not permitted for API key '{key_name}'. "
                            f"Allowed models: {allowed}"
                        )
                    }
                }
            else:
                detail = {
                    "error": {
                        "message": (
                            f"Model '{requested_model}' is not permitted for API key '{key_name}'. "
                            f"Allowed models: {allowed}"
                        ),
                        "type": "invalid_request_error",
                        "param": "model",
                        "code": "model_not_allowed"
                    }
                }

            return HTTPException(status_code=403, detail=detail)

        return None

    @classmethod
    def record_usage(cls, key_id: Optional[int], model: str, prompt_tokens: int, completion_tokens: int):
        """Records token accounting into pg_api_key_usage."""
        if key_id is not None and key_id > 0:
            db.record_api_key_tokens(
                key_id=key_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model
            )
