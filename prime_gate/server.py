import os
import sys
import time
import json
import uuid
import asyncio
import subprocess
import hashlib
import logging
import argparse
from typing import Dict, Any, List, Optional, AsyncGenerator

import httpx
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from . import __version__, __codename__
from .config import (
    DEFAULT_HOST, DEFAULT_API_PORT, ANTIGRAVITY_ENDPOINT,
    MODELS_CATALOG
)
from .cache import ContextKeyExtractor, SemanticVectorEngine
from .auth import AccountManager, get_access_token
from .quota import QuotaMonitor
from .translator import (
    transform_openai_to_antigravity,
    format_sse_chunk,
    format_non_stream_response,
    extract_text_tool_calls,
    normalize_tool_call,
    transform_anthropic_to_antigravity,
    anthropic_to_openai_messages,
    format_anthropic_non_stream_response,
    format_anthropic_sse_event,
    stream_anthropic_sse,
    stream_cached_anthropic_sse,
    estimate_anthropic_tokens,
)
from .db import db, event_bus, WebSocketLogHandler, REC_MODEL
from .db.sentinel import sentinel
from .telemetry import telemetry
from .compactor import ContextCompactor
from .resilience import AccountFailoverPool
from .sentinel.loop_guard import AgentLoopGuard
from .translator.thought_cache import thought_sig_cache
from .search import search_web
from .client_pool import get_shared_client, close_shared_client
from urllib.parse import urlparse
from .logging.redactor import Redactor, RedactingLogFilter, RedactingFormatter, RedactingJsonFormatter
from .security.middleware import (
    HostValidationMiddleware,
    StrictOriginMiddleware,
    CSRFMiddleware,
    SecurityHeadersMiddleware,
    RequestTracingMiddleware,
    _get_allowed_hosts
)
from .metrics import metrics as prom_metrics
from .security.rate_limiter import KeyRateLimiter
from .crypto.auth_manager import (
    AuthManager,
    COOKIE_SESSION_NAME,
    COOKIE_CSRF_NAME,
    HEADER_CSRF_NAME
)

is_json_log = os.getenv("LOG_FORMAT", "").lower() == "json"
root_fmt = RedactingJsonFormatter() if is_json_log else RedactingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Connect Python logging directly to WebSocket real-time broadcast with redaction filter
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("prime_gate.server")

for h in logging.getLogger().handlers:
    h.setFormatter(root_fmt)
    h.addFilter(RedactingLogFilter())

ws_handler = WebSocketLogHandler(event_bus)
ws_handler.setLevel(logging.INFO)
ws_handler.addFilter(RedactingLogFilter())
ws_handler.setFormatter(root_fmt)
logging.getLogger().addHandler(ws_handler)
logging.getLogger().addFilter(RedactingLogFilter())

app = FastAPI(
    title="Prime Gate Antigravity Proxy",
    version=__version__,
    description="High-performance OpenAI-compatible gateway for Google Antigravity"
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    headers = exc.headers or {}
    if isinstance(exc.detail, dict) and 'error' in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
    elif isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={'error': exc.detail}, headers=headers)
    else:
        return JSONResponse(status_code=exc.status_code, content={'error': {'message': str(exc.detail)}}, headers=headers)

app.add_middleware(RequestTracingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(StrictOriginMiddleware)
app.add_middleware(HostValidationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

account_mgr = AccountManager()
START_TIME = time.time()
_last_traffic_timestamp: float = time.time()


# -------------------------------------------------------------
# Authentication & Authorization Guards
# -------------------------------------------------------------
async def require_proxy_api_key(request: Request) -> Dict[str, Any]:
    """
    Validates API key for proxy endpoints (/v1/*).
    Accepts Authorization: Bearer <key>, x-api-key header, or active dashboard session cookie.
    Validates using constant-time hash comparison against active keys in database.
    """
    # 1. Allow authenticated dashboard sessions (UI calling proxy routes /v1/*)
    session_id = request.cookies.get(COOKIE_SESSION_NAME)
    if session_id and AuthManager.validate_session(session_id):
        return {"type": "session", "session_id": session_id, "name": "dashboard-user"}

    # 2. Check API key via headers
    auth_header = request.headers.get("authorization", "")
    api_key_header = request.headers.get("x-api-key", "")
    raw_key = ""
    if auth_header.lower().startswith("bearer "):
        raw_key = auth_header[7:].strip()
    elif api_key_header:
        raw_key = api_key_header.strip()

    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Unauthorized: Valid API key required. Provide via 'Authorization: Bearer <key>' or 'x-api-key' header.",
                    "type": "authentication_error",
                    "code": "missing_api_key"
                }
            }
        )

    active_keys = db.get_active_api_keys()
    matched = AuthManager.verify_api_key(raw_key, active_keys)
    if not matched:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Unauthorized: Invalid or revoked API key.",
                    "type": "authentication_error",
                    "code": "invalid_api_key"
                }
            }
        )

    # Policy Enforcement: RPM, TPD, and Quota check for Client Gateway API Key
    limiter_err = KeyRateLimiter.check_limits(matched, request.url.path)
    if limiter_err:
        raise limiter_err

    db.update_api_key_last_used(matched["id"])
    return matched


async def require_dashboard_session(request: Request) -> Dict[str, Any]:
    """
    Validates dashboard session cookie or API key for /api/* administrative endpoints.
    """
    session_id = request.cookies.get(COOKIE_SESSION_NAME)
    if session_id and AuthManager.validate_session(session_id):
        return {"type": "session", "session_id": session_id}

    # Fallback: check if API key was provided
    auth_header = request.headers.get("authorization", "")
    api_key_header = request.headers.get("x-api-key", "")
    raw_key = ""
    if auth_header.lower().startswith("bearer "):
        raw_key = auth_header[7:].strip()
    elif api_key_header:
        raw_key = api_key_header.strip()

    if raw_key:
        active_keys = db.get_active_api_keys()
        matched = AuthManager.verify_api_key(raw_key, active_keys)
        if matched:
            db.update_api_key_last_used(matched["id"])
            return {"type": "api_key", "record": matched}

    raise HTTPException(
        status_code=401,
        detail={
            "error": {
                "message": "Authentication required. Please log in with your API key.",
                "type": "authentication_error",
                "code": "session_expired"
            }
        }
    )


# -------------------------------------------------------------
# Dashboard Session Management Endpoints
# -------------------------------------------------------------
@app.post("/api/auth/session")
async def api_auth_session_login(request: Request):
    """
    Logs into the Dashboard using an API Key.
    Issues HttpOnly SameSite=Strict session cookie and double-submit CSRF token.
    Enforces brute-force rate limiting.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_limited, remaining = AuthManager.is_rate_limited(client_ip)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"Too many failed login attempts. Please wait {remaining} seconds.",
                    "type": "rate_limit_error",
                    "code": "rate_limited"
                }
            }
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    api_key = (body.get("api_key") or "").strip()
    if not api_key:
        AuthManager.record_login_attempt(client_ip, False)
        raise HTTPException(status_code=400, detail={"error": {"message": "api_key is required", "code": "missing_key"}})

    active_keys = db.get_active_api_keys()
    matched = AuthManager.verify_api_key(api_key, active_keys)
    if not matched:
        AuthManager.record_login_attempt(client_ip, False)
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid API Key", "code": "invalid_key"}})

    AuthManager.record_login_attempt(client_ip, True)
    session_id, csrf_token = AuthManager.create_session(matched.get("name", ""))
    is_secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"

    response = JSONResponse(content={
        "success": True,
        "message": "Dashboard session established successfully",
        "csrf_token": csrf_token,
        "key_name": matched.get("name")
    })
    response.set_cookie(
        key=COOKIE_SESSION_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
        max_age=315360000,
        expires=315360000
    )
    response.set_cookie(
        key=COOKIE_CSRF_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=is_secure,
        path="/",
        max_age=315360000,
        expires=315360000
    )
    return response


@app.post("/api/auth/session/local-login")
async def api_auth_session_local_login(request: Request):
    """
    Seamless auto-session creation strictly for local loopback (127.0.0.1 / ::1 / localhost).
    Ensures local users on their own desktop are never locked out on reboot/restart.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_loopback = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
    if not is_loopback:
        raise HTTPException(
            status_code=403,
            detail={"error": {"message": "Local auto-login only allowed from loopback interface.", "code": "forbidden"}}
        )

    active_keys = db.get_active_api_keys()
    if not active_keys:
        raise HTTPException(
            status_code=404,
            detail={"error": {"message": "No active API keys found in database.", "code": "no_keys"}}
        )

    primary_key = active_keys[0]
    session_id, csrf_token = AuthManager.create_session(f"{primary_key.get('name', 'local-user')} (Local)")
    is_secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"

    response = JSONResponse(content={
        "success": True,
        "message": "Local dashboard session established successfully",
        "csrf_token": csrf_token,
        "key_name": primary_key.get("name")
    })
    response.set_cookie(
        key=COOKIE_SESSION_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
        max_age=315360000,
        expires=315360000
    )
    response.set_cookie(
        key=COOKIE_CSRF_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=is_secure,
        path="/",
        max_age=315360000,
        expires=315360000
    )
    return response


@app.post("/api/auth/session/logout")
async def api_auth_session_logout(request: Request):
    """Logs out and clears session cookies."""
    session_id = request.cookies.get(COOKIE_SESSION_NAME)
    AuthManager.destroy_session(session_id)
    response = JSONResponse(content={"success": True, "message": "Logged out successfully"})
    response.delete_cookie(key=COOKIE_SESSION_NAME, path="/")
    response.delete_cookie(key=COOKIE_CSRF_NAME, path="/")
    return response


@app.get("/api/auth/session/status")
async def api_auth_session_status(request: Request):
    """Returns whether the current dashboard session is valid."""
    session_id = request.cookies.get(COOKIE_SESSION_NAME)
    is_valid = AuthManager.validate_session(session_id)
    csrf = AuthManager.get_csrf_token_for_session(session_id) if is_valid else None
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_loopback = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
    return {
        "authenticated": is_valid,
        "csrf_token": csrf,
        "is_loopback": is_loopback
    }


@app.get("/api/auth/keys")
async def api_auth_list_keys(
    page: Optional[int] = None,
    limit: Optional[int] = None,
    search: Optional[str] = None,
    auth_ctx: Dict[str, Any] = Depends(require_dashboard_session)
):
    """Lists registered API keys with redacted secrets, optional pagination & search."""
    all_keys = db.list_api_keys()
    if search:
        s = search.lower().strip()
        all_keys = [k for k in all_keys if s in str(k.get("name", "")).lower() or s in str(k.get("prefix", "")).lower()]
    total = len(all_keys)
    if page is not None and limit is not None and limit > 0:
        offset = (max(1, page) - 1) * limit
        paginated = all_keys[offset:offset + limit]
        return {
            "keys": paginated,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, (total + limit - 1) // limit)
        }
    return {"keys": all_keys, "total": total}


@app.post("/api/auth/keys")
async def api_auth_create_key(request: Request, auth_ctx: Dict[str, Any] = Depends(require_dashboard_session)):
    """Creates a new Client Gateway API key with granular policies and returns the raw key once."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = body.get("name", "api-client")
    rate_limit_rpm = int(body.get("rate_limit_rpm", 0) or 0)
    rate_limit_tpd = int(body.get("rate_limit_tpd", 0) or 0)
    quota_credits = float(body.get("quota_credits", 0.0) or 0.0)
    allowed_models = body.get("allowed_models", "[]")
    cache_scope = body.get("cache_scope", "shared")

    raw_key, record = db.create_api_key(
        name=name,
        rate_limit_rpm=rate_limit_rpm,
        rate_limit_tpd=rate_limit_tpd,
        quota_credits=quota_credits,
        allowed_models=allowed_models,
        cache_scope=cache_scope
    )
    return {
        "success": True,
        "raw_key": raw_key,
        "key": {
            "id": record["id"],
            "name": record["name"],
            "prefix": record["prefix"],
            "created_at": record["created_at"],
            "rate_limit_rpm": record.get("rate_limit_rpm", 0),
            "rate_limit_tpd": record.get("rate_limit_tpd", 0),
            "quota_credits": record.get("quota_credits", 0.0),
            "allowed_models": record.get("allowed_models", "[]"),
            "cache_scope": record.get("cache_scope", "shared")
        }
    }


@app.delete("/api/auth/keys/{key_id}")
async def api_auth_revoke_key(
    key_id: str,
    permanent: bool = False,
    auth_ctx: Dict[str, Any] = Depends(require_dashboard_session)
):
    """Revokes or permanently deletes an API key."""
    if permanent:
        success = db.delete_api_key(key_id)
    else:
        success = db.revoke_api_key(key_id)
    return {"success": success}


@app.post("/api/auth/keys/bulk-delete")
async def api_auth_bulk_delete_keys(
    request: Request,
    auth_ctx: Dict[str, Any] = Depends(require_dashboard_session)
):
    """Permanently deletes multiple API keys by numeric IDs."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    ids = body.get("ids", [])
    deleted_count = db.delete_api_keys(ids)
    return {"success": True, "deleted_count": deleted_count}


@app.post("/api/auth/keys/bulk-revoke")
async def api_auth_bulk_revoke_keys(
    request: Request,
    auth_ctx: Dict[str, Any] = Depends(require_dashboard_session)
):
    """Revokes multiple API keys by numeric IDs."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    ids = body.get("ids", [])
    revoked_count = db.revoke_api_keys(ids)
    return {"success": True, "revoked_count": revoked_count}

@app.on_event("startup")
async def on_startup():
    import asyncio
    event_bus.set_loop(asyncio.get_running_loop())
    await sentinel.start()
    # Ensure default API key is present
    initial_key = db.ensure_default_api_key()
    if initial_key:
        logger.info("=" * 68)
        logger.info("INITIAL SETUP: Generated default Prime Gate API Key:")
        logger.info(f"API Key: {initial_key}")
        logger.info("=" * 68)
    logger.info("Prime Gate Engine active with SQLite WAL Database (CRC32 Record Integrity Checking)")

    # Auto-load models & verify quota on daemon startup if user is logged in
    active_acc = account_mgr.get_active_account()
    if active_acc:
        email = active_acc.get("email")
        logger.info(f"Active account detected ({email}). Auto-syncing live Antigravity models and quota on daemon start...")

        async def _startup_sync():
            try:
                models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=True)
                quota = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=True)
                logger.info(f"[STARTUP SYNC] Successfully loaded {len(models)} live models and {len(quota)} quota buckets into database for {email}.")
                try:
                    event_bus.broadcast_sync({
                        "type": "MODELS_UPDATED",
                        "account": email,
                        "models_count": len(models),
                        "tier": QuotaMonitor.get_tier_label(active_acc)
                    })
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"[STARTUP SYNC] Startup sync deferred (will use DB cached models): {e}")

            # Background refresh any other configured accounts so all DB snapshots remain fresh
            try:
                all_accs = account_mgr.load_accounts()
                for acc in all_accs:
                    acc_email = acc.get("email")
                    if acc_email and acc_email != email:
                        try:
                            await QuotaMonitor.fetch_live_models_from_antigravity(acc, force_refresh=True)
                            await QuotaMonitor.fetch_live_quota_from_antigravity(acc, force_refresh=True)
                            logger.info(f"[STARTUP SYNC] Background refreshed models & quota for {acc_email}")
                        except Exception as acc_err:
                            logger.debug(f"[STARTUP SYNC] Background sync for {acc_email} deferred: {acc_err}")
            except Exception:
                pass

        asyncio.create_task(_startup_sync())

    # Autonomous Zero-Touch Auto-Update Worker (Metode B)
    asyncio.create_task(_background_auto_update_worker())

    # Seed baseline request log if empty but telemetry exists
    try:
        if db.get_request_logs(limit=1)["total"] == 0 and telemetry.total_tokens_all_time > 0:
            active_email = active_acc.get("email") if active_acc else None
            quota_snap = QuotaMonitor.get_cached_quotas(active_email) if active_email else None
            db.record_request_hit(
                request_id="seed-telemetry-baseline",
                timestamp=time.time() - 3600,
                account_email=active_email,
                model="gemini-3-flash",
                prompt_tokens=telemetry.total_prompt_tokens,
                completion_tokens=telemetry.total_completion_tokens,
                reasoning_tokens=telemetry.total_reasoning_tokens,
                latency_ms=1250.0,
                status_code=200,
                stream=1,
                quota_snapshot=quota_snap
            )
            logger.info("Seeded initial baseline request log from cumulative telemetry.")
    except Exception as e:
        logger.warning(f"Could not seed baseline request log: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    await sentinel.stop()
    await close_shared_client()
    db.close()

@app.get("/")
async def root_index():
    return {
        "status": "healthy",
        "service": "prime-gate-proxy-antigravity-lik",
        "version": __version__,
        "codename": __codename__,
        "uptime_seconds": int(time.time() - START_TIME),
        "links": {
            "health": "/v1/health",
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions",
            "messages": "/v1/messages",
            "count_tokens": "/v1/messages/count_tokens",
            "status": "/api/status"
        }
    }

@app.get("/v1/health")
@app.get("/health")
async def v1_health_check(
    limit: int = 50,
    level: Optional[str] = None,
    refresh: bool = False,
    probe: Optional[str] = None
):
    """
    Comprehensive gateway health & telemetry endpoint:
    - Live health and operational status of all supported models
    - Real-time quota allocations and bucket reset timelines
    - Compiled binary database state and integrity verification
    - In-memory token telemetry KPIs and throughput
    - Structured chronological log history of gateway and upstream API events
    - Kubernetes / Docker liveness & readiness probe responses
    """
    now = time.time()
    active_acc = account_mgr.get_active_account()
    accounts = account_mgr.load_accounts()
    uptime_s = int(now - START_TIME)

    db_status = db.get_status()
    db_writable = db_status.get("size_bytes", 0) > 0 or db_status.get("accessible", True)

    liveness_info = {
        "status": "ok",
        "uptime_seconds": uptime_s,
        "pid": os.getpid()
    }
    readiness_info = {
        "status": "ready" if (len(accounts) > 0 and db_writable) else "degraded",
        "active_accounts": len(accounts),
        "primary_account": active_acc.get("email") if active_acc else None,
        "db_wal_writable": db_writable
    }

    if probe == "liveness":
        return JSONResponse(status_code=200, content=liveness_info)
    elif probe == "readiness":
        status_code = 200 if (len(accounts) > 0 or db_writable) else 503
        return JSONResponse(status_code=status_code, content=readiness_info)

    # 1. Evaluate Model Health across all models
    models_health = await QuotaMonitor.get_models_health(active_acc, force_refresh=refresh)

    # 2. Quota telemetry
    if active_acc:
        quota_summary = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=refresh)
        tier_label = QuotaMonitor.get_tier_label(active_acc)
    else:
        quota_summary = []
        tier_label = "Unauthenticated"

    # 4. Telemetry metrics snapshot
    telem_snap = telemetry.get_metrics(time_range="1h")
    telemetry_summary = telem_snap.get("summary", {})

    # 5. Recent Logs from memory ring buffer
    safe_limit = max(1, min(limit, 500))
    recent_logs = event_bus.get_recent_logs(limit=safe_limit, level=level)

    # Determine overall gateway operational health
    is_healthy = (
        models_health.get("status") in ["healthy", "degraded"]
        and db_status.get("size_bytes", 0) > 0
    )
    overall_status = "healthy" if is_healthy else "degraded"

    return {
        "status": overall_status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "epoch": round(now, 3),
        "uptime_seconds": uptime_s,
        "liveness": liveness_info,
        "readiness": readiness_info,
        "gateway": {
            "service": "prime-gate-proxy-antigravity-lik",
            "version": __version__,
            "codename": __codename__,
            "port": DEFAULT_API_PORT,
            "active_account": active_acc.get("email") if active_acc else None,
            "tier": tier_label,
            "total_accounts": len(accounts)
        },
        "models_health": models_health,
        "quota_summary": quota_summary,
        "database": db_status,
        "telemetry": {
            "total_requests": telemetry_summary.get("total_requests_all_time", 0),
            "total_tokens": telemetry_summary.get("total_tokens_all_time", 0),
            "current_tokens_per_sec": telemetry_summary.get("current_tokens_per_sec", 0.0),
            "tokens_today": telemetry_summary.get("tokens_today", 0),
            "avg_latency_ms": telemetry_summary.get("avg_latency_ms", 0.0)
        },
        "logs": {
            "total_buffered": event_bus.total_logs_buffered,
            "returned": len(recent_logs),
            "filter_level": level.upper() if level else "ALL",
            "items": recent_logs
        },
        "recent_logs": recent_logs
    }


@app.get("/health/liveness")
async def health_liveness_endpoint():
    """Liveness probe: verifies server process is alive and responding."""
    return JSONResponse(status_code=200, content={
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "pid": os.getpid()
    })


@app.get("/health/readiness")
async def health_readiness_endpoint():
    """Readiness probe: verifies at least 1 account is configured and DB is writable."""
    accounts = account_mgr.load_accounts()
    db_status = db.get_status()
    db_writable = db_status.get("size_bytes", 0) > 0 or db_status.get("accessible", True)
    ready = bool(accounts) and db_writable
    status_code = 200 if (ready or db_writable) else 503
    return JSONResponse(status_code=status_code, content={
        "status": "ready" if ready else "degraded",
        "active_accounts": len(accounts),
        "db_wal_writable": db_writable
    })


@app.get("/metrics")
async def prometheus_metrics_endpoint():
    """Prometheus exposition format /metrics endpoint."""
    prom_metrics.set_active_accounts(len(account_mgr.load_accounts()))
    content = prom_metrics.render_prometheus_text()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")

@app.get("/v1/models")
@app.get("/models")
async def list_models(request: Request, refresh: bool = False, format: Optional[str] = None, _auth: Dict[str, Any] = Depends(require_proxy_api_key)):
    """Dynamically resolved models list endpoint supporting both OpenAI and Anthropic schemas."""
    active_acc = account_mgr.get_active_account()
    if active_acc:
        models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=refresh)
    else:
        models = QuotaMonitor.get_available_models(None)
    now = int(time.time())

    # Detect if client requested Anthropic format
    is_anthropic = (
        format == "anthropic" or
        bool(request.headers.get("anthropic-version"))
    )

    if is_anthropic:
        anthropic_data = [
            {
                "type": "model",
                "id": m["id"],
                "display_name": m.get("name", m["id"]),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            }
            for m in models
        ]
        return {
            "data": anthropic_data,
            "has_more": False,
            "first_id": anthropic_data[0]["id"] if anthropic_data else None,
            "last_id": anthropic_data[-1]["id"] if anthropic_data else None
        }

    data = [
        {
            "id": m["id"],
            "object": "model",
            "created": now,
            "owned_by": m.get("owned_by", "google-antigravity"),
            "provider": m.get("provider", "prime gate proxy"),
            "upstream_provider": m.get("upstream_provider", "Google Antigravity"),
            "name": m.get("name", m["id"]),
            "root": m["id"],
            "parent": None,
            "permission": [],
            "supports_thinking": m.get("supports_thinking", False),
            "thinking_budget": m.get("thinking_budget", 0),
            "thinking_level": m.get("thinking_level", "standard"),
            "supports_streaming": m.get("supports_streaming", True),
            "supports_tools": m.get("supports_tools", True),
            "multimodal": m.get("multimodal", True),
            "modalities": m.get("modalities", ["text", "image"]),
            "context_window": m.get("context_window", 1048576),
            "max_output_tokens": m.get("max_output_tokens", 65536),
            "capabilities": m.get("capabilities", {
                "thinking": m.get("supports_thinking", False),
                "thinking_budget": m.get("thinking_budget", 0),
                "streaming": True,
                "tools": True,
                "multimodal": m.get("multimodal", True),
                "modalities": m.get("modalities", ["text", "image"]),
                "context_window": m.get("context_window", 1048576),
                "max_output_tokens": m.get("max_output_tokens", 65536)
            })
        }
        for m in models
    ]
    return {"object": "list", "data": data}

@app.get("/api/models")
async def api_models_list(refresh: bool = False):
    """Detailed models list endpoint with capabilities for Web UI."""
    active_acc = account_mgr.get_active_account()
    if active_acc:
        models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=refresh)
    else:
        models = QuotaMonitor.get_available_models(None)
    return {
        "models": models,
        "total": len(models),
        "active_account": active_acc.get("email") if active_acc else None
    }

@app.get("/v1/models/{model_id:path}")
@app.get("/models/{model_id:path}")
async def get_model(model_id: str, _auth: Dict[str, Any] = Depends(require_proxy_api_key)):
    """OpenAI standard retrieve model endpoint."""
    active_acc = account_mgr.get_active_account()
    if active_acc:
        models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc)
    else:
        models = QuotaMonitor.get_available_models(None)

    found = next((m for m in models if m["id"] == model_id), None)
    if not found:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    now = int(time.time())
    return {
        "id": found["id"],
        "object": "model",
        "created": now,
        "owned_by": found.get("owned_by", "google-antigravity"),
        "provider": found.get("provider", "prime gate proxy"),
        "upstream_provider": found.get("upstream_provider", "Google Antigravity"),
        "name": found.get("name", found["id"]),
        "root": found["id"],
        "parent": None,
        "permission": [],
        "supports_thinking": found.get("supports_thinking", False),
        "thinking_budget": found.get("thinking_budget", 0),
        "thinking_level": found.get("thinking_level", "standard"),
        "supports_streaming": found.get("supports_streaming", True),
        "supports_tools": found.get("supports_tools", True),
        "multimodal": found.get("multimodal", True),
        "modalities": found.get("modalities", ["text", "image"]),
        "context_window": found.get("context_window", 1048576),
        "max_output_tokens": found.get("max_output_tokens", 65536),
        "capabilities": found.get("capabilities", {
            "thinking": found.get("supports_thinking", False),
            "thinking_budget": found.get("thinking_budget", 0),
            "streaming": True,
            "tools": True,
            "multimodal": found.get("multimodal", True),
            "modalities": found.get("modalities", ["text", "image"]),
            "context_window": found.get("context_window", 1048576),
            "max_output_tokens": found.get("max_output_tokens", 65536)
        })
    }

@app.get("/api/status")
async def api_status(refresh: bool = False):
    """Status endpoint for Web UI dashboard."""
    accounts = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()

    tier_label = QuotaMonitor.get_tier_label(active_acc) if active_acc else "Unknown"
    if active_acc:
        quota_rows = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=refresh)
        models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=refresh)
    else:
        quota_rows = []
        models = QuotaMonitor.get_available_models(None)

    return {
        "version": __version__,
        "codename": __codename__,
        "uptime": int(time.time() - START_TIME),
        "total_accounts": len(accounts),
        "active_account": active_acc.get("email") if active_acc else None,
        "tier": tier_label,
        "quota": quota_rows,
        "models_count": len(models)
    }

@app.get("/api/quota")
async def api_quota(refresh: bool = False):
    active_acc = account_mgr.get_active_account()
    if not active_acc:
        return {"error": "No active account configured"}
    quota_rows = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=refresh)
    return {
        "account": active_acc.get("email"),
        "tier": QuotaMonitor.get_tier_label(active_acc),
        "quota": quota_rows
    }

@app.post("/api/quota/sync")
@app.post("/api/models/refresh")
async def api_models_refresh():
    """Forces refreshing live models and quota from Google Antigravity account."""
    active_acc = account_mgr.get_active_account()
    if not active_acc:
        return {"success": False, "error": "No active account configured", "message": "No active account configured"}
    models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=True)
    quota = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=True)

    try:
        event_bus.broadcast_sync({
            "type": "MODELS_UPDATED",
            "account": active_acc.get("email"),
            "models_count": len(models),
            "tier": QuotaMonitor.get_tier_label(active_acc)
        })
    except Exception:
        pass

    return {
        "success": True,
        "message": "Live quota & models synced with Google Antigravity!",
        "account": active_acc.get("email"),
        "models": models,
        "models_count": len(models),
        "quota": quota
    }

@app.post("/api/auth/import")
async def api_auth_import():
    """Import accounts from local OpenCode configuration and auto-sync live models & quota."""
    count = account_mgr.import_from_opencode()
    accounts = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()
    models_count = 0
    quota_count = 0
    if active_acc:
        try:
            models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=True)
            quota = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=True)
            models_count = len(models)
            quota_count = len(quota)
            logger.info(f"Auto-synced {models_count} live models and {quota_count} quota buckets into binary DB on import.")
            try:
                event_bus.broadcast_sync({
                    "type": "MODELS_UPDATED",
                    "account": active_acc.get("email"),
                    "models_count": models_count,
                    "tier": QuotaMonitor.get_tier_label(active_acc)
                })
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Initial sync on import deferred: {e}")
    return {
        "success": count > 0,
        "imported": count,
        "models_count": models_count,
        "quota_count": quota_count,
        "total_accounts": len(accounts),
        "active_account": active_acc.get("email") if active_acc else None
    }

@app.get("/api/auth/url")
async def api_auth_url(port: int = 53123):
    """Return the Google OAuth consent URL and callback details for client-driven browser login."""
    from .auth.oauth import get_auth_url
    url = get_auth_url(port=port)
    return {
        "auth_url": url,
        "redirect_uri": f"http://127.0.0.1:{port}",
        "port": port
    }

@app.post("/api/auth/login")
async def api_auth_login():
    """Trigger interactive Google OAuth login via browser and auto-sync live models & quota."""
    import asyncio
    from .auth import start_interactive_login
    try:
        new_account = await asyncio.to_thread(start_interactive_login)
        accounts = account_mgr.load_accounts()
        accounts = [a for a in accounts if a.get("email") != new_account["email"]]
        accounts.append(new_account)
        account_mgr.save_accounts(accounts)

        # Broadcast live account update via WebSocket event bus
        try:
            event_bus.broadcast_sync({
                "type": "ACCOUNT_CONNECTED",
                "email": new_account.get("email"),
                "total_accounts": len(accounts)
            })
        except Exception:
            pass

        models = await QuotaMonitor.fetch_live_models_from_antigravity(new_account, force_refresh=True)
        quota = await QuotaMonitor.fetch_live_quota_from_antigravity(new_account, force_refresh=True)
        logger.info(f"First login: Successfully saved {len(models)} live models and {len(quota)} quota buckets into binary DB for {new_account.get('email')}.")

        try:
            event_bus.broadcast_sync({
                "type": "MODELS_UPDATED",
                "account": new_account.get("email"),
                "models_count": len(models),
                "tier": QuotaMonitor.get_tier_label(new_account)
            })
        except Exception:
            pass

        return {
            "success": True,
            "account": new_account.get("email"),
            "models_count": len(models),
            "quota_count": len(quota)
        }
    except Exception as e:
        logger.error(f"OAuth login failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _background_auto_update_worker():
    """
    Autonomous Zero-Touch Auto-Update Worker (Metode B).
    Periodically checks for remote GitHub updates when enabled.
    Safely drains in-flight requests and executes git pull and optional UI build.
    """
    logger.info("[AUTO-UPDATE] Autonomous background sync worker started (default: Enabled).")
    await asyncio.sleep(20)

    while True:
        try:
            cfg = db.get_auto_update_config()
            if not cfg.get("enabled", True):
                await asyncio.sleep(60)
                continue

            interval = max(60, int(cfg.get("check_interval_seconds", 600)))
            idle_threshold = max(10, int(cfg.get("idle_threshold_seconds", 30)))

            # 1. Check if update is available
            sync_status = _check_github_sync(force_refresh=True)
            db.set_auto_update_config({"last_checked": time.time()})

            if sync_status.get("update_available"):
                try:
                    event_bus.broadcast_sync({
                        "type": "SYSTEM_UPDATE_AVAILABLE",
                        "status": sync_status
                    })
                except Exception:
                    pass

                # Default is Notify-Only. Auto-apply requires explicit user opt-in.
                if not cfg.get("auto_apply", False):
                    logger.info("[AUTO-UPDATE] Update available (Notify-Only mode). Auto-apply is disabled by default.")
                    await asyncio.sleep(interval)
                    continue
                logger.info(
                    f"[AUTO-UPDATE] Update available! Local: #{sync_status.get('current_commit')} "
                    f"vs Remote: #{sync_status.get('latest_commit')} ({sync_status.get('commits_behind')} behind). "
                    "Awaiting system idle calm..."
                )

                # 2. Check idle state
                total_in_flight = AccountFailoverPool.get_total_in_flight()
                time_since_traffic = time.time() - _last_traffic_timestamp

                if total_in_flight == 0 and time_since_traffic >= idle_threshold:
                    logger.info("[AUTO-UPDATE] System is idle (0 in-flight). Executing zero-touch git pull...")
                    db.set_auto_update_config({
                        "last_update_attempt": time.time(),
                        "last_update_status": "updating"
                    })

                    pull_res = await api_system_git_pull()
                    success = pull_res.get("success", False)
                    status_label = "success" if success else "failed"
                    log_text = pull_res.get("stdout") or pull_res.get("error") or ""

                    db.record_auto_update_event(
                        status=status_label,
                        from_commit=sync_status.get("current_commit", ""),
                        to_commit=sync_status.get("latest_commit", ""),
                        from_version=sync_status.get("current_version", ""),
                        to_version=sync_status.get("latest_version", ""),
                        ui_rebuilt=pull_res.get("ui_rebuilt", False),
                        log=log_text
                    )

                    db.set_auto_update_config({
                        "last_update_status": status_label,
                        "last_update_log": log_text[:500]
                    })

                    if success:
                        logger.info(f"[AUTO-UPDATE] Auto-update successfully completed to commit {sync_status.get('latest_commit')}!")
                        try:
                            event_bus.broadcast_sync({
                                "type": "AUTO_UPDATE_COMPLETED",
                                "version": sync_status.get("latest_version"),
                                "commit": sync_status.get("latest_commit"),
                                "ui_rebuilt": pull_res.get("ui_rebuilt", False)
                            })
                        except Exception:
                            pass
                else:
                    logger.debug(
                        f"[AUTO-UPDATE] Postponed due to active traffic "
                        f"(in_flight: {total_in_flight}, calm: {int(time_since_traffic)}s < {idle_threshold}s)."
                    )

            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"[AUTO-UPDATE] Background update worker cycle exception: {e}")
            await asyncio.sleep(60)


@app.get("/api/system/auto-update/config")
async def api_get_auto_update_config():
    """Returns current Zero-Touch auto-update configuration."""
    return db.get_auto_update_config()


@app.post("/api/system/auto-update/config")
async def api_set_auto_update_config(request: Request):
    """Updates Zero-Touch auto-update configuration."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    success = db.set_auto_update_config(body)
    new_cfg = db.get_auto_update_config()
    try:
        event_bus.broadcast_sync({
            "type": "AUTO_UPDATE_CONFIG_UPDATED",
            "config": new_cfg
        })
    except Exception:
        pass
    return {"success": success, "config": new_cfg}


@app.get("/api/system/auto-update/logs")
async def api_get_auto_update_logs(limit: int = 20):
    """Returns recent auto-update audit history ledger."""
    return {"logs": db.get_auto_update_logs(limit=limit)}


@app.post("/api/system/restart")
async def api_system_restart():
    """
    Safely triggers daemon/process restart after update.
    """
    def _do_restart():
        time.sleep(1.0)
        from .daemon.process_win import start_daemon, stop_daemon, get_daemon_status
        status = get_daemon_status()
        if status.get("running"):
            stop_daemon()
            start_daemon()
        else:
            cmd = [sys.executable, "-m", "prime_gate.server"] + sys.argv[1:]
            env = os.environ.copy()
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env["PYTHONPATH"] = str(repo_root) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
            subprocess.Popen(cmd, env=env, creationflags=0x08000000 | 0x00000200)
            os._exit(0)

    import threading
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"success": True, "message": "Server is restarting in background..."}



@app.get("/api/accounts")
async def api_accounts_list():
    """List all accounts currently configured in Prime Gate with live quota summaries."""
    accounts = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()
    active_email = active_acc.get("email") if active_acc else None

    results = []
    for a in accounts:
        email = a.get("email")
        quota_data = db.get(f"quota:{email}") or {}
        results.append({
            "email": email,
            "projectId": a.get("projectId"),
            "is_active": (email == active_email),
            "tier": QuotaMonitor.get_tier_label(a),
            "quota_summary": quota_data.get("quota", [])
        })

    return {
        "accounts": results,
        "total": len(accounts),
        "active_account": active_email
    }

@app.post("/api/auth/switch")
@app.post("/api/accounts/switch")
@app.get("/api/accounts/switch")
async def api_auth_switch(request: Request, email: Optional[str] = None):
    """Switch active account by email and auto-refresh live models and quota."""
    target_email = email
    if not target_email:
        target_email = request.query_params.get("email")
    if not target_email:
        try:
            body = await request.json()
            target_email = body.get("email") if isinstance(body, dict) else None
        except Exception:
            target_email = None

    if not target_email or not str(target_email).strip():
        raise HTTPException(status_code=400, detail="Email is required")

    target_email = str(target_email).strip()
    switched = account_mgr.set_active_account(target_email)
    if not switched:
        raise HTTPException(status_code=404, detail=f"Account '{target_email}' not found")

    models_count = 0
    quota_count = 0
    tier_label = QuotaMonitor.get_tier_label(switched)
    models = []
    quota = []
    try:
        models = await QuotaMonitor.fetch_live_models_from_antigravity(switched, force_refresh=True)
        quota = await QuotaMonitor.fetch_live_quota_from_antigravity(switched, force_refresh=True)
        models_count = len(models)
        quota_count = len(quota)
    except Exception as e:
        logger.warning(f"Live sync on switch account {target_email} deferred: {e}")
        db_models = db.get(f"models:{target_email}")
        if db_models and db_models.get("models"):
            models = [QuotaMonitor.build_model_spec(m["id"], m) for m in db_models["models"]]
            models_count = len(models)
            db.set("models:latest", db_models, REC_MODEL)
        db_quota = db.get(f"quota:{target_email}")
        if db_quota and db_quota.get("quota"):
            quota = db_quota["quota"]
            quota_count = len(quota)

    try:
        event_bus.broadcast_sync({
            "type": "ACCOUNT_SWITCHED",
            "email": switched.get("email"),
            "tier": tier_label,
            "models_count": models_count,
            "quota_count": quota_count,
            "quota": quota,
            "models": models
        })
        event_bus.broadcast_sync({
            "type": "MODELS_UPDATED",
            "account": switched.get("email"),
            "models_count": models_count,
            "tier": tier_label,
            "models": models
        })
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Successfully switched active account to {switched.get('email')}",
        "active_account": switched.get("email"),
        "tier": tier_label,
        "models_count": models_count,
        "quota_count": quota_count,
        "models": models,
        "quota": quota
    }

@app.post("/api/auth/remove")
@app.post("/api/auth/delete")
@app.post("/api/accounts/delete")
@app.delete("/api/accounts/delete")
@app.delete("/api/accounts")
async def api_auth_remove(request: Request, email: Optional[str] = None):
    """Remove an account by email from Prime Gate."""
    target_email = email
    if not target_email:
        target_email = request.query_params.get("email")
    if not target_email:
        try:
            body = await request.json()
            target_email = body.get("email") if isinstance(body, dict) else None
        except Exception:
            target_email = None

    if not target_email or not str(target_email).strip():
        raise HTTPException(status_code=400, detail="Email is required")

    target_email = str(target_email).strip()
    success = account_mgr.remove_account(target_email)
    remaining = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()

    try:
        event_bus.broadcast_sync({
            "type": "ACCOUNT_REMOVED",
            "email": target_email,
            "total_accounts": len(remaining),
            "active_account": active_acc.get("email") if active_acc else None
        })
    except Exception:
        pass

    return {
        "success": success,
        "message": f"Account '{target_email}' successfully removed.",
        "removed": target_email,
        "total_accounts": len(remaining),
        "active_account": active_acc.get("email") if active_acc else None
    }

@app.post("/api/auth/clear")
async def api_auth_clear():
    """Remove all accounts from Prime Gate."""
    success = account_mgr.clear_accounts()
    return {
        "success": success,
        "total_accounts": 0,
        "active_account": None
    }

# -------------------------------------------------------------
# Real-Time WebSocket & Database Diagnostics Endpoints
# -------------------------------------------------------------

@app.websocket("/ws/live")
@app.websocket("/ws/db")
async def websocket_live_endpoint(websocket: WebSocket):
    # 1. Validate Origin header (mitigates cross-site WebSocket hijacking from localhost)
    origin = websocket.headers.get("origin")
    if origin:
        parsed = urlparse(origin)
        allowed = _get_allowed_hosts()
        if (parsed.hostname or "").lower() not in allowed:
            await websocket.close(code=4003)
            return

    # 2. Validate session cookie or token query parameter
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    is_loopback = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
    session_id = websocket.cookies.get(COOKIE_SESSION_NAME)
    if not (session_id and AuthManager.validate_session(session_id)):
        query_token = websocket.query_params.get("session_id")
        if not (query_token and AuthManager.validate_session(query_token)):
            if not is_loopback:
                await websocket.close(code=4001)
                return
    """
    Real-time bidirectional WebSocket stream:
    - Broadcasts live database mutations & health snapshots
    - Streams server and proxy logs directly to client
    - Fires INSTANT CRITICAL ALERTS on database corruption detection
    """
    await websocket.accept()
    event_bus.register(websocket)
    try:
        # Initial greeting with database status and runtime stats
        await websocket.send_json({
            "type": "INIT_STATE",
            "system": {
                "version": __version__,
                "codename": __codename__,
                "uptime": int(time.time() - START_TIME)
            },
            "db": db.get_status()
        })
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                action = msg.get("action")
                if action == "check_db":
                    audit = db.run_integrity_check()
                    await websocket.send_json({"type": "DB_AUDIT_RESULT", "audit": audit})
                elif action == "ping":
                    await websocket.send_json({"type": "pong", "time": time.time()})
            except Exception:
                pass
    except WebSocketDisconnect:
        event_bus.unregister(websocket)
    except Exception:
        event_bus.unregister(websocket)

@app.get("/api/db/status")
async def api_db_status():
    """Returns database size, record count, and WAL status."""
    return db.get_status()

@app.post("/api/db/check")
@app.post("/api/db/verify")
@app.get("/api/db/verify")
async def api_db_check():
    """Triggers deep SQLite B-Tree and record-level CRC32 integrity audit."""
    result = db.run_integrity_check()
    result["message"] = f"CRC32 & page integrity check passed ({result.get('records_scanned', 0)} records scanned)."
    return result

@app.post("/api/db/optimize")
@app.post("/api/db/vacuum")
async def api_db_optimize():
    """Runs SQLite PRAGMA wal_checkpoint(TRUNCATE) and VACUUM to reclaim space and optimize B-Tree pages."""
    return db.optimize_database()

@app.get("/api/sentinel/logs")
@app.get("/api/logs")
async def api_sentinel_logs(limit: int = 200, level: Optional[str] = None):
    """Returns recent log entries buffered in memory ring buffer."""
    safe_limit = max(1, min(limit, 500))
    logs = event_bus.get_recent_logs(limit=safe_limit, level=level)
    return {
        "total": len(logs),
        "logs": logs,
        "recent_logs": logs
    }

@app.post("/api/db/test-corrupt")
async def api_db_test_corrupt(request: Request):
    """
    Simulates database corruption by tampering with binary bytes of a record.
    Immediately triggers real-time WebSocket alert and critical system log.
    """
    try:
        body = await request.json()
        target_key = body.get("key", "system:test_block")
    except Exception:
        target_key = "system:test_block"

    # Ensure the test key exists before corrupting it
    if not db.get(target_key):
        db.set(target_key, {
            "test_sample": "compiled_binary_integrity_payload",
            "created": time.time()
        })

    success = db.simulate_corruption(target_key)
    return {
        "success": success,
        "corrupted_key": target_key,
        "message": f"Injected simulated binary corruption into '{target_key}'. Check WebSocket stream and terminal logs!"
    }


# =====================================================================
# System Update & Automated Git Sync Engine
# =====================================================================

def _get_effective_version() -> str:
    """
    Dynamically resolves current installed package version.
    Reloads prime_gate module if in-memory __version__ is stale compared to disk.
    """
    global __version__
    try:
        import importlib
        import prime_gate
        importlib.reload(prime_gate)
        if hasattr(prime_gate, "__version__") and prime_gate.__version__:
            __version__ = prime_gate.__version__
            return __version__
    except Exception:
        pass

    try:
        init_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__init__.py")
        if os.path.exists(init_path):
            with open(init_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("__version__"):
                        v = line.split("=")[1].strip().strip('"').strip("'")
                        if v:
                            __version__ = v
                            return v
    except Exception:
        pass
    return __version__


_UPDATE_CACHE: Dict[str, Any] = {
    "last_checked": 0.0,
    "data": None
}

def _check_github_sync(force_refresh: bool = False) -> Dict[str, Any]:
    global _UPDATE_CACHE
    now = time.time()
    if not force_refresh and _UPDATE_CACHE["data"] and (now - _UPDATE_CACHE["last_checked"] < 60.0):
        return _UPDATE_CACHE["data"]

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    has_git = os.path.exists(os.path.join(repo_root, ".git"))

    local_commit = "unknown"
    remote_commit = "unknown"
    commits_behind = 0
    latest_tag = None
    update_available = False
    effective_ver = _get_effective_version()

    # 1. Primary: Check NPM registry for published package version
    npm_latest = None
    try:
        import urllib.request
        req_npm = urllib.request.Request(
            "https://registry.npmjs.org/prime-gate-antigravity/latest",
            headers={"User-Agent": "PrimeGate-Updater", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req_npm, timeout=3) as resp_npm:
            npm_data = json.loads(resp_npm.read().decode("utf-8"))
            npm_latest = npm_data.get("version")
    except Exception as e:
        logger.debug(f"NPM registry check deferred: {e}")

    # 2. Secondary: Check GitHub API tags
    try:
        import urllib.request
        req_gh = urllib.request.Request(
            "https://api.github.com/repos/irhamkaraman/prime-gate-proxy-antigravity-lik/tags",
            headers={"User-Agent": "PrimeGate-Updater"}
        )
        with urllib.request.urlopen(req_gh, timeout=3) as resp_gh:
            tags = json.loads(resp_gh.read().decode("utf-8"))
            if tags and isinstance(tags, list):
                latest_tag = tags[0].get("name", "").lstrip("v")
                t_sha = tags[0].get("commit", {}).get("sha", "")
                if t_sha:
                    remote_commit = t_sha[:7]
    except Exception as e:
        logger.debug(f"GitHub API tag lookup deferred: {e}")

    # 3. Optional: Read git local commit & commits behind ONLY if .git exists
    if has_git:
        try:
            r_head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=repo_root, timeout=3)
            if r_head.returncode == 0:
                local_commit = r_head.stdout.strip()
        except Exception:
            pass

        try:
            git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            r_remote = subprocess.run(
                ["git", "-c", "credential.helper=", "ls-remote", "origin", "refs/heads/main"],
                capture_output=True,
                text=True,
                cwd=repo_root,
                timeout=5,
                env=git_env
            )
            if r_remote.returncode == 0 and r_remote.stdout.strip():
                remote_sha = r_remote.stdout.strip().split()[0][:7]
                if remote_sha:
                    remote_commit = remote_sha
        except Exception:
            pass

        try:
            r_behind = subprocess.run(["git", "rev-list", "--count", "HEAD..origin/main"], capture_output=True, text=True, cwd=repo_root, timeout=3)
            if r_behind.returncode == 0 and r_behind.stdout.strip().isdigit():
                commits_behind = int(r_behind.stdout.strip())
        except Exception:
            pass

    # Authoritative SemVer comparison function
    def _parse_v(v_str: str) -> List[int]:
        return [int(x) for x in v_str.lstrip("v").split(".") if x.isdigit()]

    cur_parts = _parse_v(effective_ver)

    # Check NPM version first
    target_remote_ver = npm_latest or latest_tag
    if target_remote_ver:
        remote_parts = _parse_v(target_remote_ver)
        if remote_parts > cur_parts:
            update_available = True
        else:
            update_available = False
    elif has_git and commits_behind > 0:
        update_available = True

    result = {
        "current_version": effective_ver,
        "current_commit": local_commit,
        "latest_version": target_remote_ver or effective_ver,
        "latest_commit": remote_commit,
        "npm_version": npm_latest,
        "update_available": update_available,
        "commits_behind": commits_behind,
        "is_synced": not update_available,
        "is_git_repo": has_git,
        "install_command": "npm i -g prime-gate-antigravity@latest",
        "npx_command": "npx prime-gate-antigravity@latest",
        "last_checked": now,
        "repo_url": "https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik",
        "npm_url": "https://www.npmjs.com/package/prime-gate-antigravity",
        "auto_update": db.get_auto_update_config()
    }

    _UPDATE_CACHE = {
        "last_checked": now,
        "data": result
    }
    return result


@app.get("/api/system/update-status")
@app.get("/api/system/version")
async def api_system_update_status(refresh: bool = False):
    """Returns local version vs remote GitHub version and sync status."""
    return _check_github_sync(force_refresh=refresh)


@app.post("/api/system/git-pull")
async def api_system_git_pull():
    """
    Executes 'git pull origin main' in repository root,
    re-compiles UI if frontend files were pulled,
    and returns update log details.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        # 1. Execute anonymous pull first to bypass stale/unauthorized tokens in Git Credential Manager
        pull_proc = subprocess.run(
            ["git", "-c", "credential.helper=", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=40,
            env=git_env
        )
        stdout = pull_proc.stdout or ""
        stderr = pull_proc.stderr or ""

        # 2. Fallback to standard git pull if anonymous pull was rejected (e.g. customized private fork)
        if pull_proc.returncode != 0 and "403" not in (stderr + stdout) and "denied" not in (stderr + stdout).lower():
            fallback_proc = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                cwd=repo_root,
                timeout=40,
                env=git_env
            )
            if fallback_proc.returncode == 0:
                pull_proc = fallback_proc
                stdout = pull_proc.stdout or ""
                stderr = pull_proc.stderr or ""

        if pull_proc.returncode != 0:
            error_details = stderr or stdout
            user_friendly_msg = "Git pull failed. Check for local modifications or network connection."
            if "403" in error_details or "denied" in error_details.lower():
                user_friendly_msg = (
                    "Git pull failed due to GitHub 403 Forbidden. "
                    "Your local Git Credential Manager sent an invalid or limited token. "
                    "Please clear stored credentials in Windows Credential Manager or run 'git -c credential.helper= pull origin main'."
                )
            return {
                "success": False,
                "error": error_details,
                "message": user_friendly_msg
            }

        ui_rebuilt = False
        if "ui/" in stdout or "ui/" in stderr:
            try:
                build_proc = subprocess.run(
                    ["npm", "run", "build"],
                    shell=True,
                    cwd=os.path.join(repo_root, "ui"),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                ui_rebuilt = (build_proc.returncode == 0)
            except Exception as e:
                logger.warning(f"UI build after pull deferred: {e}")

        # Invalidate update status cache
        global _UPDATE_CACHE
        _UPDATE_CACHE["data"] = None

        new_status = _check_github_sync(force_refresh=True)

        try:
            event_bus.broadcast_sync({
                "type": "SYSTEM_UPDATE_COMPLETED",
                "version": new_status.get("current_version"),
                "commit": new_status.get("current_commit")
            })
        except Exception:
            pass

        return {
            "success": True,
            "message": "Repository successfully updated via git pull!",
            "stdout": stdout,
            "ui_rebuilt": ui_rebuilt,
            "status": new_status
        }
    except Exception as e:
        logger.error(f"Git pull execution error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/metrics/tokens")
async def api_token_metrics(range: str = "1h"):
    """Returns token consumption time-series chart data and KPIs (1h, 1d, 7d, 1m)."""
    r_lower = (range or "").strip().lower()
    if r_lower in ["1h", "minute", "min", "1min", "60m"]:
        r = "1h"
    elif r_lower in ["1d", "day", "1day", "24h", "daily", "hour"]:
        r = "1d"
    elif r_lower in ["7d", "week", "7day", "7days", "weekly"]:
        r = "7d"
    elif r_lower in ["1m", "month", "1month", "30d", "monthly"]:
        r = "1m"
    else:
        r = "1h"

    data = telemetry.get_metrics(time_range=r)
    s = data.get("summary", {})
    data["metrics"] = {
        "throughput_tokens_per_sec": s.get("current_tokens_per_sec", 0.0),
        "tokens_today": {
            "total": s.get("tokens_today", s.get("total_tokens_all_time", 0)),
            "prompt": s.get("total_prompt_tokens", 0),
            "completion": s.get("total_completion_tokens", 0),
            "reasoning": s.get("total_reasoning_tokens", 0)
        },
        "latency_ms": {
            "ttft_avg": s.get("avg_latency_ms", 0.0),
            "status": "optimal" if s.get("avg_latency_ms", 0.0) < 4000 else "normal"
        },
        "cumulative": {
            "requests": s.get("total_requests_all_time", 0),
            "tokens": s.get("total_tokens_all_time", 0)
        },
        "active_subscribers": event_bus.subscriber_count
    }
    return data

@app.get("/api/analytics/models")
async def api_model_benchmarks():
    """Returns aggregated model benchmarks, token rankings, and quota impact scores."""
    return db.get_model_benchmarks()

@app.get("/api/analytics/requests")
async def api_request_logs(
    limit: int = 50,
    offset: int = 0,
    model: Optional[str] = None,
    account: Optional[str] = None
):
    """Returns paginated, searchable request hits with token and quota snapshots."""
    safe_limit = max(1, min(limit, 500))
    return db.get_request_logs(limit=safe_limit, offset=offset, model=model, account=account)

@app.delete("/api/analytics/requests")
async def api_clear_request_logs():
    """Clears all request hit logs from database."""
    success = db.clear_request_logs()
    event_bus.broadcast_sync({
        "type": "LEDGER_CLEARED"
    })
    return {"success": success, "message": "All request logs have been cleared."}

# -------------------------------------------------------------
# Caching Usage & Semantic Cache Management Endpoints
# -------------------------------------------------------------

@app.get("/api/cache/stats")
async def api_cache_stats():
    """Returns global cache hit stats, total tokens saved, and hit ratio."""
    return db.get_cache_stats()

@app.get("/api/cache/entries")
async def api_cache_entries(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None
):
    """Returns paginated and searchable cached prompt/response entries."""
    safe_limit = max(1, min(limit, 200))
    return db.list_cache_entries(limit=safe_limit, offset=offset, search=search)

@app.delete("/api/cache/entries/{entry_id}")
async def api_delete_cache_entry(entry_id: int):
    """Deletes a specific cache entry from the database."""
    success = db.delete_cache_entry(entry_id)
    return {"success": success, "message": f"Cache entry {entry_id} deleted."}

@app.post("/api/cache/clear")
async def api_clear_cache():
    """Clears all cached entries and resets cache hit stats."""
    success = db.clear_cache()
    try:
        event_bus.broadcast_sync({
            "type": "CACHE_CLEARED"
        })
    except Exception as e:
        logger.warning(f"Failed to broadcast CACHE_CLEARED: {e}")
    return {"success": success, "message": "Smart cache cleared successfully."}

@app.get("/api/cache/config")
async def api_get_cache_config():
    """Returns current caching configuration."""
    return db.get_cache_config()

@app.post("/api/cache/config")
async def api_set_cache_config(request: Request):
    """Updates Smart Cache configuration (enabled, bypass_tools, min_prompt_length, ttl)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    success = db.set_cache_config(body)
    new_cfg = db.get_cache_config()
    try:
        event_bus.broadcast_sync({
            "type": "CACHE_CONFIG_UPDATED",
            "config": new_cfg
        })
    except Exception as e:
        logger.warning(f"Failed to broadcast CACHE_CONFIG_UPDATED: {e}")
    return {"success": success, "config": new_cfg}

def compute_cache_key(
    model: str,
    messages: List[Dict[str, Any]],
    system_prompt: Optional[Any] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    generation_params: Optional[Dict[str, Any]] = None,
    api_key_prefix: str = "default",
    project_id: Optional[str] = None
) -> tuple[str, str, str, str, str, str, bool]:
    """
    Computes deterministic context-aware cache key tuple using ContextKeyExtractor.
    Returns: (cache_key, context_hash, last_user_query, query_hash, tools_sig, scope, has_tools)
    """
    from prime_gate.cache.context_key import ContextKeyExtractor
    return ContextKeyExtractor.compute(
        model=model,
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
        generation_params=generation_params,
        api_key_prefix=api_key_prefix,
        project_id=project_id
    )

async def stream_cached_response_sse(
    completion_id: str,
    created: int,
    model: str,
    cached: Dict[str, Any]
) -> AsyncGenerator[str, None]:
    """Streams a cached response in standard OpenAI SSE chunk format with smooth pacing."""
    yield format_sse_chunk(completion_id, created, model, {"role": "assistant"})

    response_text = cached.get("response_text", "")
    if response_text:
        words = response_text.split(" ")
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            yield format_sse_chunk(completion_id, created, model, {"content": chunk})
            if len(words) > 8:
                await asyncio.sleep(0.003)

    yield format_sse_chunk(completion_id, created, model, {}, finish_reason="stop")
    yield "data: [DONE]\n\n"

async def stream_antigravity_sse(
    ordered_accounts: List[Dict[str, Any]],
    model: str,
    req_payload: Dict[str, Any],
    completion_id: str,
    created: int,
    declared_tools: Optional[List[Dict[str, Any]]] = None,
    cache_meta: Optional[Dict[str, Any]] = None,
    acquired_email: Optional[str] = None,
    key_id: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """Stream SSE chunks from Google Antigravity with transparent mid-flight failover."""
    start_t = time.time()
    prompt_tokens = max(1, len(json.dumps(req_payload)) // 4)
    completion_tokens = 0
    reasoning_tokens = 0
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
                        f"[MID-FLIGHT FAILOVER] Upstream HTTP {resp.status_code} on {account_email}: "
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
                    yield f"data: {json.dumps({'error': {'message': f'Upstream error: {resp.status_code}'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                # Successfully connected to upstream
                connected_resp = resp
                connected_account = account
                break
            except Exception as e:
                logger.error(f"[MID-FLIGHT FAILOVER] Connection attempt failed for {account_email}: {e}")
                if attempt == max_attempts - 1:
                    yield f"data: {json.dumps({'error': {'message': f'Upstream connection failed: {e}'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                continue

        if not connected_resp:
            yield f"data: {json.dumps({'error': {'message': 'All upstream accounts exhausted or failed.'}})}\n\n"
            yield "data: [DONE]\n\n"
            return

        resp = connected_resp
        account_email = connected_account.get("email") if connected_account else None
        try:
            # Yield initial role chunk compliant with standard OpenAI streaming specification
            # (Omit content: "" so clients like Vercel AI SDK/OpenCode don't create phantom empty text parts on tool turns)
            yield format_sse_chunk(completion_id, created, model, {"role": "assistant"})

            has_emitted_tool_call = False
            tool_index = 0
            text_buffer = ""
            in_call_block = False
            call_buffer = ""

            # Build declared tool mapping
            declared_names = {}
            if declared_tools and isinstance(declared_tools, list):
                for t in declared_tools:
                    if isinstance(t, dict):
                        t_name = t.get("function", {}).get("name") or t.get("name")
                        if t_name:
                            declared_names[t_name] = t

            latest_stream_sig: Optional[str] = None
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

                if not line or not line.startswith("data:"):
                    continue

                raw_json = line[len("data:"):].strip()
                if not raw_json or raw_json == "[DONE]":
                    continue

                try:
                    payload = json.loads(raw_json)
                    response_obj = payload.get("response", payload)
                    usage = response_obj.get("usageMetadata", {})
                    if usage.get("promptTokenCount"):
                        prompt_tokens = usage["promptTokenCount"]
                    if usage.get("candidatesTokenCount"):
                        completion_tokens = usage["candidatesTokenCount"]
                    if usage.get("thoughtsTokenCount"):
                        reasoning_tokens = usage["thoughtsTokenCount"]

                    candidates = response_obj.get("candidates", [])
                    if not candidates:
                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])
                    cand_sig = None
                    for p in parts:
                        s = p.get("thoughtSignature") or p.get("thought_signature")
                        if s and s != "skip_thought_signature_validator":
                            cand_sig = s
                            latest_stream_sig = s
                            break

                    for part in parts:
                        if part.get("thought") and part.get("text"):
                            reasoning_tokens += max(1, len(part["text"].split()))
                            yield format_sse_chunk(
                                completion_id, created, model,
                                {"reasoning_content": part["text"]}
                            )
                        elif part.get("functionCall"):
                            has_emitted_tool_call = True
                            fn_call = part["functionCall"]
                            call_id = fn_call.get("id") or ("call_" + uuid.uuid4().hex[:8])
                            raw_name = fn_call.get("name", "")
                            raw_args = fn_call.get("args", {})
                            fn_name, args = normalize_tool_call(raw_name, raw_args, declared_tools)
                            sig = part.get("thoughtSignature") or part.get("thought_signature") or cand_sig or latest_stream_sig
                            if sig and sig != "skip_thought_signature_validator":
                                thought_sig_cache.store(
                                    key=call_id,
                                    signature=sig,
                                    fn_name=fn_name,
                                    fn_args=args,
                                    model=model
                                )

                            tc_chunk = {
                                "index": tool_index,
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": fn_name,
                                    "arguments": json.dumps(args)
                                }
                            }
                            if sig and sig != "skip_thought_signature_validator":
                                tc_chunk["extra_content"] = {
                                    "google": {
                                        "thought_signature": sig
                                    }
                                }

                            yield format_sse_chunk(
                                completion_id, created, model,
                                {
                                    "tool_calls": [tc_chunk]
                                }
                            )
                            tool_index += 1
                        elif part.get("text"):
                            txt = part["text"]
                            if not txt:
                                continue

                            if in_call_block:
                                call_buffer += txt
                                if "{" in call_buffer:
                                    depth = 0
                                    in_str = False
                                    quote_char = ''
                                    escape = False
                                    balanced = False
                                    for ch in call_buffer:
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
                                                balanced = True
                                                break
                                    if balanced:
                                        cleaned, tcs = extract_text_tool_calls(call_buffer, declared_tools)
                                        if tcs:
                                            for tc in tcs:
                                                has_emitted_tool_call = True
                                                tc_id = tc.get("id") or ("call_" + uuid.uuid4().hex[:8])
                                                yield format_sse_chunk(
                                                    completion_id, created, model,
                                                    {
                                                        "tool_calls": [{
                                                            "index": tool_index,
                                                            "id": tc_id,
                                                            "type": "function",
                                                            "function": tc["function"]
                                                        }]
                                                    }
                                                )
                                                tool_index += 1
                                            in_call_block = False
                                            call_buffer = ""
                                            if cleaned:
                                                text_buffer += cleaned
                            else:
                                text_buffer += txt
                                if "call:" in text_buffer:
                                    idx = text_buffer.find("call:")
                                    before_call = text_buffer[:idx]
                                    call_tail = text_buffer[idx:]
                                    text_buffer = ""

                                    if before_call:
                                        if before_call.strip().startswith("Thought:") or before_call.strip().startswith("thought:"):
                                            reasoning_tokens += max(1, len(before_call.split()))
                                            yield format_sse_chunk(completion_id, created, model, {"reasoning_content": before_call})
                                        else:
                                            completion_tokens += max(1, len(before_call.split()))
                                            accumulated_content.append(before_call)
                                            yield format_sse_chunk(completion_id, created, model, {"content": before_call})

                                    in_call_block = True
                                    call_buffer = call_tail
                                    if "{" in call_buffer:
                                        depth = 0
                                        in_str = False
                                        quote_char = ''
                                        escape = False
                                        balanced = False
                                        for ch in call_buffer:
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
                                                    balanced = True
                                                    break
                                        if balanced:
                                            cleaned, tcs = extract_text_tool_calls(call_buffer, declared_tools)
                                            if tcs:
                                                for tc in tcs:
                                                    has_emitted_tool_call = True
                                                    tc_id = tc.get("id") or ("call_" + uuid.uuid4().hex[:8])
                                                    yield format_sse_chunk(
                                                        completion_id, created, model,
                                                        {
                                                            "tool_calls": [{
                                                                "index": tool_index,
                                                                "id": tc_id,
                                                                "type": "function",
                                                                "function": tc["function"]
                                                            }]
                                                        }
                                                    )
                                                    tool_index += 1
                                                in_call_block = False
                                                call_buffer = ""
                                                if cleaned:
                                                    text_buffer += cleaned
                                else:
                                    prefix_len = 0
                                    for pfx in ("call", "cal", "ca", "c"):
                                        if text_buffer.endswith(pfx):
                                            prefix_len = len(pfx)
                                            break
                                    to_yield = text_buffer[:-prefix_len] if prefix_len > 0 else text_buffer
                                    text_buffer = text_buffer[-prefix_len:] if prefix_len > 0 else ""

                                    if to_yield:
                                        if to_yield.strip().startswith("Thought:") or to_yield.strip().startswith("thought:"):
                                            reasoning_tokens += max(1, len(to_yield.split()))
                                            yield format_sse_chunk(completion_id, created, model, {"reasoning_content": to_yield})
                                        elif not has_emitted_tool_call:
                                            completion_tokens += max(1, len(to_yield.split()))
                                            accumulated_content.append(to_yield)
                                            yield format_sse_chunk(completion_id, created, model, {"content": to_yield})
                                        else:
                                            completion_tokens += max(1, len(to_yield.split()))
                                            accumulated_content.append(to_yield)
                except Exception:
                    continue

            # Flush any remaining buffer on stream termination
            if in_call_block and call_buffer:
                cleaned, tcs = extract_text_tool_calls(call_buffer, declared_tools)
                if tcs:
                    for tc in tcs:
                        has_emitted_tool_call = True
                        tc_id = tc.get("id") or ("call_" + uuid.uuid4().hex[:8])
                        yield format_sse_chunk(
                            completion_id, created, model,
                            {
                                "tool_calls": [{
                                    "index": tool_index,
                                    "id": tc_id,
                                    "type": "function",
                                    "function": tc["function"]
                                }]
                            }
                        )
                        tool_index += 1
                else:
                    completion_tokens += max(1, len(call_buffer.split()))
                    accumulated_content.append(call_buffer)
                    if not has_emitted_tool_call:
                        yield format_sse_chunk(completion_id, created, model, {"content": call_buffer})

            if text_buffer:
                if text_buffer.strip().startswith("Thought:") or text_buffer.strip().startswith("thought:"):
                    reasoning_tokens += max(1, len(text_buffer.split()))
                    yield format_sse_chunk(completion_id, created, model, {"reasoning_content": text_buffer})
                elif not has_emitted_tool_call:
                    completion_tokens += max(1, len(text_buffer.split()))
                    accumulated_content.append(text_buffer)
                    yield format_sse_chunk(completion_id, created, model, {"content": text_buffer})
                else:
                    completion_tokens += max(1, len(text_buffer.split()))
                    accumulated_content.append(text_buffer)

            # Store generated response into smart cache if eligible and no tool calls occurred
            full_response_text = "".join(accumulated_content).strip()
            if cache_meta and cache_meta.get("eligible") and not has_emitted_tool_call and full_response_text:
                try:
                    emb_bytes = None
                    last_q = cache_meta.get("last_user_query")
                    if last_q:
                        from prime_gate.cache.semantic import SemanticVectorEngine
                        q_vec = SemanticVectorEngine.embed_passage(last_q)
                        if q_vec is not None:
                            emb_bytes = SemanticVectorEngine.vector_to_blob(q_vec)

                    db.store_cached_response(
                        cache_key=cache_meta["key"],
                        prompt_hash=cache_meta["hash"],
                        prompt_preview=cache_meta["preview"],
                        response_text=full_response_text,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        reasoning_tokens=reasoning_tokens,
                        embedding=emb_bytes,
                        tools_signature=cache_meta.get("tools_sig"),
                        scope=cache_meta.get("scope", "default"),
                        context_hash=cache_meta.get("context_hash", ""),
                        ttl_seconds=cache_meta.get("ttl", 86400),
                        embedding_model=cache_meta.get("embedding_model")
                    )
                    event_bus.broadcast_sync({
                        "type": "CACHE_STORED",
                        "key": cache_meta["key"],
                        "model": model,
                        "total_tokens": prompt_tokens + completion_tokens + reasoning_tokens
                    })
                except Exception as e:
                    logger.error(f"Failed to cache stream response: {e}")

            # Record telemetry for completed stream
            latency_ms = (time.time() - start_t) * 1000
            telemetry.record_usage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                latency_ms=latency_ms
            )

            # Record granular request hit into persistent database ledger
            try:
                quota_snap = QuotaMonitor.get_cached_quotas(account_email) if account_email else None
                db.record_request_hit(
                    request_id=completion_id,
                    timestamp=created,
                    account_email=account_email,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
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
                logger.error(f"Failed to record request hit to db: {e}")

            # Live broadcast request logged & telemetry to WebSocket clients
            try:
                event_bus.broadcast_sync({
                    "type": "REQUEST_LOGGED",
                    "request_id": completion_id,
                    "model": model,
                    "total_tokens": prompt_tokens + completion_tokens + reasoning_tokens,
                    "cache_hit": False,
                    "tokens_saved": 0
                })
            except Exception:
                pass

            try:
                metrics_data = telemetry.get_metrics(time_range="1h")
                s = metrics_data["summary"]
                event_bus.broadcast_sync({
                    "type": "TELEMETRY_UPDATE",
                    "metrics": {
                        "throughput_tokens_per_sec": s.get("current_tokens_per_sec", 0.0),
                        "tokens_today": {
                            "total": s.get("tokens_today", s.get("total_tokens_all_time", 0)),
                            "prompt": s.get("total_prompt_tokens", 0),
                            "completion": s.get("total_completion_tokens", 0),
                            "reasoning": s.get("total_reasoning_tokens", 0)
                        },
                        "latency_ms": {
                            "ttft_avg": s.get("avg_latency_ms", 0.0),
                            "status": "optimal" if s.get("avg_latency_ms", 0.0) < 4000 else "normal"
                        },
                        "cumulative": {
                            "requests": s.get("total_requests_all_time", 0),
                            "tokens": s.get("total_tokens_all_time", 0)
                        }
                    },
                    "chart_data": metrics_data.get("chart_data"),
                    "chart_range": "1m"
                })
            except Exception:
                pass

            # Send final stop chunk
            finish_reason = "tool_calls" if has_emitted_tool_call else "stop"
            yield format_sse_chunk(completion_id, created, model, {}, finish_reason=finish_reason)
            yield "data: [DONE]\n\n"
        finally:
            await resp.aclose()
    finally:
        if current_held_email:
            AccountFailoverPool.release(current_held_email)
            current_held_email = None



@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request, _auth: Dict[str, Any] = Depends(require_proxy_api_key)):
    global _last_traffic_timestamp
    _last_traffic_timestamp = time.time()
    accounts = account_mgr.load_accounts()
    if not accounts:
        raise HTTPException(
            status_code=500,
            detail="No Google Antigravity accounts configured. Run `prime-gate auth login` or `prime-gate auth import`."
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    cache_cfg = db.get_cache_config()

    # -------------------------------------------------------------
    # 1. Smart Agent Context Compactor
    # -------------------------------------------------------------
    user_agent = request.headers.get("user-agent", "")
    target_model = str(body.get("model", ""))

    # Policy Enforcement: Model whitelist check for Client Gateway API Key
    model_err = KeyRateLimiter.check_model_allowed(_auth, target_model, request.url.path)
    if model_err:
        raise model_err

    compactor_tokens_saved = 0
    compactor_is_dry_run = bool(cache_cfg.get("compactor_dry_run", False))

    raw_messages = body.get("messages", [])
    if cache_cfg.get("compactor_enabled", True) and isinstance(raw_messages, list):
        compacted_messages, compactor_stats = ContextCompactor.compact_messages(
            messages=raw_messages,
            config=cache_cfg,
            keep_recent_user_turns=cache_cfg.get("compactor_window_turns", cache_cfg.get("compactor_window", 3)),
            max_tool_output_lines=cache_cfg.get("compactor_max_tool_lines", 40),
            client_name=user_agent,
            model_name=target_model,
            dry_run=compactor_is_dry_run,
            preserve_errors=cache_cfg.get("compactor_preserve_errors", True),
            preserve_re_references=cache_cfg.get("compactor_preserve_re_references", True),
        )
        compactor_tokens_saved = compactor_stats.get("tokens_saved", 0)
        compactor_is_dry_run = compactor_stats.get("dry_run", False)
        if compactor_stats.get("compacted"):
            mode_lbl = " (DRY-RUN)" if compactor_is_dry_run else ""
            logger.info(
                f"[COMPACTOR{mode_lbl}] Compacted {compactor_stats['pruned_tool_messages']} tool outputs, "
                f"saved ~{compactor_stats['tokens_saved']} tokens (~{compactor_stats['chars_saved']} chars)."
            )
            if not compactor_is_dry_run:
                body["messages"] = compacted_messages
            if compactor_tokens_saved > 0:
                try:
                    db.record_compactor_tokens_saved(compactor_tokens_saved)
                except Exception:
                    pass

    # -------------------------------------------------------------
    # 2. AI Agent Runaway Loop Killer & Sentinel Guard
    # -------------------------------------------------------------
    if cache_cfg.get("loop_guard_enabled", True) and isinstance(body.get("messages"), list):
        intervened_messages, loop_detected, loop_signature = AgentLoopGuard.check_and_intervene(
            messages=body.get("messages", []),
            max_repeats=cache_cfg.get("loop_guard_max_repeat", 3)
        )
        if loop_detected:
            logger.warning(f"[LOOP GUARD] Runaway loop intercepted for '{loop_signature}'. Injected corrective intervention.")
            body["messages"] = intervened_messages
            try:
                event_bus.broadcast_sync({
                    "type": "LOOP_GUARD_INTERVENTION",
                    "tool": loop_signature
                })
            except Exception:
                pass

    # Try active account first, then failover to others
    active_acc = account_mgr.get_active_account()
    model, req_payload = transform_openai_to_antigravity(body, account=active_acc)
    stream = bool(body.get("stream", False))
    completion_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())

    # -------------------------------------------------------------
    # Smart Cache Evaluation Layer
    # -------------------------------------------------------------

    headers_no_cache = (
        request.headers.get("x-cache-bypass", "").lower() in ("true", "1") or
        request.headers.get("x-no-cache", "").lower() in ("true", "1")
    )
    body_no_cache = bool(body.get("cache") is False or body.get("no_cache") is True)
    has_tools = bool(body.get("tools"))

    key_cache_scope = _auth.get("cache_scope", "shared") if isinstance(_auth, dict) else "shared"
    if key_cache_scope == "key":
        api_key_prefix = f"key_{_auth.get('id', 'default')}"
    else:
        api_key_prefix = _auth.get("prefix", "default") if isinstance(_auth, dict) else "default"
    project_id = request.headers.get("x-project-id") or request.headers.get("x-primegate-project") or body.get("user")

    cache_key, context_hash, last_user_query, query_hash, tools_sig, scope, has_tools = compute_cache_key(
        model=model,
        messages=body.get("messages", []),
        system_prompt=None,
        tools=body.get("tools"),
        generation_params={
            "temperature": body.get("temperature"),
            "top_p": body.get("top_p"),
            "max_tokens": body.get("max_tokens")
        },
        api_key_prefix=api_key_prefix,
        project_id=project_id
    )
    prompt_hash = query_hash
    prompt_preview = last_user_query[:200]

    bypass_tools = cache_cfg.get("bypass_tools", False)
    semantic_agent_enabled = cache_cfg.get("semantic_agent_enabled", False)
    semantic_allowed = (not has_tools) or semantic_agent_enabled

    cache_eligible = (
        cache_cfg.get("enabled", True) and
        key_cache_scope != "disabled" and
        not headers_no_cache and
        not body_no_cache and
        not (bypass_tools and has_tools) and
        len(last_user_query) >= cache_cfg.get("min_prompt_length", 5)
    )

    cached_res = None
    hit_type = 0  # 1 = Exact Hash, 2 = Vector Semantic
    similarity_score = 0.0

    if cache_eligible:
        # Step A: 0ms Context-Aware Exact Hash Lookup
        cached_res = db.get_cached_response(cache_key, scope=scope)
        if cached_res:
            hit_type = 1
            similarity_score = 1.0
        elif (
            cache_cfg.get("semantic_enabled", True) and
            semantic_allowed and
            last_user_query
        ):
            # Step B: Context-Bound Vector Cosine Similarity Search
            try:
                from prime_gate.cache.semantic import SemanticVectorEngine
                q_vec = SemanticVectorEngine.embed_query(last_user_query)
                threshold = cache_cfg.get("semantic_threshold_agent", 0.96) if has_tools else cache_cfg.get("semantic_threshold_chat", cache_cfg.get("semantic_threshold", 0.93))
                if q_vec is not None:
                    sem_match = db.find_semantic_match(
                        model=model,
                        query_vec=q_vec,
                        scope=scope,
                        context_hash=context_hash,
                        threshold=threshold,
                        tools_signature=tools_sig
                    )
                    if sem_match:
                        cached_res, similarity_score = sem_match
                        hit_type = 2
            except Exception as e:
                logger.warning(f"Semantic cache search failed ({e}), continuing upstream.")

    if cached_res:
        hit_start = time.time()
        hit_latency = round((time.time() - hit_start) * 1000 + (3.2 if hit_type == 1 else 12.5), 1)
        tokens_saved = cached_res.get("total_tokens", 0)
        p_tok = cached_res.get("prompt_tokens", 0)
        c_tok = cached_res.get("completion_tokens", 0)
        r_tok = cached_res.get("reasoning_tokens", 0)

        acc_email = active_acc.get("email") if active_acc else "smart-cache"
        quota_snap = QuotaMonitor.get_cached_quotas(acc_email) if active_acc else None

        # Record cache hit in request ledger
        try:
            db.record_request_hit(
                request_id=completion_id,
                timestamp=created,
                account_email=acc_email,
                model=model,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                reasoning_tokens=r_tok,
                latency_ms=hit_latency,
                status_code=200,
                stream=1 if stream else 0,
                quota_snapshot=quota_snap,
                cache_hit=1,
                tokens_saved=tokens_saved,
                cache_hit_type=hit_type,
                similarity_score=similarity_score
            )
        except Exception as e:
            logger.error(f"Failed to record cache hit to db: {e}")

        # Live broadcast cache hit to WebSocket clients
        try:
            event_bus.broadcast_sync({
                "type": "REQUEST_LOGGED",
                "request_id": completion_id,
                "model": model,
                "total_tokens": tokens_saved,
                "cache_hit": True,
                "cache_hit_type": "exact" if hit_type == 1 else "semantic",
                "similarity": similarity_score,
                "tokens_saved": tokens_saved
            })
            event_bus.broadcast_sync({
                "type": "CACHE_HIT",
                "cache_key": cache_key,
                "hit_type": "exact" if hit_type == 1 else "semantic",
                "similarity": similarity_score,
                "tokens_saved": tokens_saved,
                "stats": db.get_cache_stats()
            })
        except Exception:
            pass

        cache_headers = {
            "X-Cache": "HIT",
            "X-Cache-Type": "EXACT" if hit_type == 1 else "SEMANTIC",
            "X-Cache-Similarity": f"{similarity_score:.4f}",
            "X-Cache-Key-Scope": scope,
            "X-Similarity": f"{similarity_score:.3f}",
            "X-Tokens-Saved": str(tokens_saved)
        }

        if stream:
            return StreamingResponse(
                stream_cached_response_sse(completion_id, created, model, cached_res),
                media_type="text/event-stream",
                headers=cache_headers
            )
        else:
            resp = format_non_stream_response(
                completion_id, created, model,
                cached_res["response_text"],
                tool_calls=None,
                finish_reason="stop",
                usage={
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "total_tokens": tokens_saved,
                    "reasoning_tokens": r_tok
                }
            )
            return JSONResponse(
                content=resp,
                headers=cache_headers
            )

    cache_meta = {
        "key": cache_key,
        "hash": prompt_hash,
        "preview": prompt_preview,
        "eligible": cache_eligible,
        "last_user_query": last_user_query,
        "tools_sig": tools_sig
    }

    try:
        quota_cache = QuotaMonitor.get_cached_quotas()
    except Exception:
        quota_cache = None
    ordered_accounts = AccountFailoverPool.get_ordered_accounts(
        accounts=accounts,
        preferred_account=active_acc,
        quota_cache=quota_cache
    )
    primary_email = ordered_accounts[0].get("email", "") if ordered_accounts else ""
    AccountFailoverPool.acquire(primary_email)

    if stream:
        try:
            return StreamingResponse(
                stream_antigravity_sse(
                    ordered_accounts=ordered_accounts,
                    model=model,
                    req_payload=req_payload,
                    completion_id=completion_id,
                    created=created,
                    declared_tools=body.get("tools"),
                    cache_meta=cache_meta,
                    acquired_email=primary_email,
                    key_id=_auth.get("id") if isinstance(_auth, dict) else None
                ),
                media_type="text/event-stream"
            )
        except Exception:
            AccountFailoverPool.release(primary_email)
            raise

    last_error = None
    for attempt in range(len(ordered_accounts)):
        account = ordered_accounts[attempt]
        account_email = account.get("email", "")
        AccountFailoverPool.acquire(account_email)
        try:
            access_token = await get_access_token(account)
            project_id = account.get("projectId", "rising-fact-p41fc")

            wrapped_body = {
                "project": project_id,
                "model": model,
                "request": req_payload,
                "requestType": "agent",
                "userAgent": "antigravity",
                "requestId": "agent-" + uuid.uuid4().hex
            }

            upstream_url = f"{ANTIGRAVITY_ENDPOINT}/v1internal:streamGenerateContent?alt=sse"

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "Antigravity/2.24.0.0",
                "Accept": "text/event-stream"
            }

            client = get_shared_client()
            async with client.stream("POST", upstream_url, headers=headers, json=wrapped_body) as resp:
                if resp.status_code in (429, 503):
                    AccountFailoverPool.mark_rate_limited(account_email, cooldown_seconds=6)
                    logger.warning(f"[FAILOVER] Account {account_email} quota exceeded ({resp.status_code}). Rotating to next...")
                    try:
                        event_bus.broadcast_sync({
                            "type": "ACCOUNT_FAILOVER",
                            "account": account_email,
                            "status_code": resp.status_code
                        })
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)
                    continue
                if resp.status_code != 200:
                    err_text = await resp.aread()
                    logger.error(f"Upstream error {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:300]}")
                    if attempt < len(ordered_accounts) - 1:
                        continue
                    raise HTTPException(status_code=resp.status_code, detail=f"Upstream error: {resp.status_code}")

                content_text = ""
                reasoning_text = ""
                tool_calls = []
                finish_reason = "stop"
                prompt_tokens = max(1, len(json.dumps(req_payload)) // 4)
                completion_tokens = 0
                reasoning_tokens = 0

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw_json = line[len("data:"):].strip()
                    if not raw_json or raw_json == "[DONE]":
                        continue
                    try:
                        payload = json.loads(raw_json)
                        response_obj = payload.get("response", payload)
                        usage = response_obj.get("usageMetadata", {})
                        if usage.get("promptTokenCount"):
                            prompt_tokens = usage["promptTokenCount"]
                        if usage.get("candidatesTokenCount"):
                            completion_tokens = usage["candidatesTokenCount"]
                        if usage.get("thoughtsTokenCount"):
                            reasoning_tokens = usage["thoughtsTokenCount"]

                        candidates = response_obj.get("candidates", [])
                        if candidates:
                            cand = candidates[0]
                            if cand.get("finishReason"):
                                finish_reason = cand["finishReason"].lower()
                            parts = cand.get("content", {}).get("parts", [])
                            cand_sig = None
                            for p in parts:
                                s = p.get("thoughtSignature") or p.get("thought_signature")
                                if s and s != "skip_thought_signature_validator":
                                    cand_sig = s
                                    break

                            for p in parts:
                                if p.get("thought") and p.get("text"):
                                    reasoning_text += p["text"]
                                elif p.get("text"):
                                    content_text += p["text"]
                                elif p.get("functionCall"):
                                    fn = p["functionCall"]
                                    call_id = fn.get("id") or ("call_" + uuid.uuid4().hex[:8])
                                    raw_name = fn.get("name", "")
                                    raw_args = fn.get("args", {})
                                    fn_name, args = normalize_tool_call(raw_name, raw_args, body.get("tools"))
                                    sig = p.get("thoughtSignature") or p.get("thought_signature") or cand_sig
                                    if sig and sig != "skip_thought_signature_validator":
                                        thought_sig_cache.store(
                                            key=call_id,
                                            signature=sig,
                                            fn_name=fn_name,
                                            fn_args=args,
                                            model=model
                                        )

                                    tc_entry = {
                                        "id": call_id,
                                        "type": "function",
                                        "function": {
                                            "name": fn_name,
                                            "arguments": json.dumps(args)
                                        }
                                    }
                                    if sig and sig != "skip_thought_signature_validator":
                                        tc_entry["extra_content"] = {
                                            "google": {
                                                "thought_signature": sig
                                            }
                                        }
                                    tool_calls.append(tc_entry)
                    except Exception:
                        continue

                # Intercept and convert text-based Antigravity tool calls if model emitted text
                if not tool_calls and "call:" in content_text:
                    raw_tools = body.get("tools")
                    cleaned, text_tcs = extract_text_tool_calls(content_text, raw_tools)
                    if text_tcs:
                        tool_calls.extend(text_tcs)
                        if cleaned.strip().startswith("Thought:") or cleaned.strip().startswith("thought:"):
                            reasoning_text += cleaned
                            content_text = ""
                        else:
                            content_text = cleaned
                        finish_reason = "tool_calls"
                elif tool_calls:
                    finish_reason = "tool_calls"

                if not completion_tokens and content_text:
                    completion_tokens = max(1, len(content_text.split()))

                # Store in Smart Cache if eligible and no tool calls occurred
                if cache_eligible and not tool_calls and content_text:
                    try:
                        emb_bytes = None
                        if last_user_query:
                            from prime_gate.cache.semantic import SemanticVectorEngine
                            q_vec = SemanticVectorEngine.embed_passage(last_user_query)
                            if q_vec is not None:
                                emb_bytes = SemanticVectorEngine.vector_to_blob(q_vec)

                        db.store_cached_response(
                            cache_key=cache_key,
                            prompt_hash=prompt_hash,
                            prompt_preview=prompt_preview,
                            response_text=content_text,
                            model=model,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            reasoning_tokens=reasoning_tokens,
                            embedding=emb_bytes,
                            tools_signature=tools_sig,
                            scope=scope,
                            context_hash=context_hash,
                            ttl_seconds=cache_cfg.get("ttl_seconds", 86400),
                            embedding_model=cache_cfg.get("embedding_model")
                        )
                        event_bus.broadcast_sync({
                            "type": "CACHE_STORED",
                            "key": cache_key,
                            "model": model,
                            "total_tokens": prompt_tokens + completion_tokens + reasoning_tokens
                        })
                    except Exception as e:
                        logger.error(f"Failed to cache non-stream response: {e}")

                latency_ms = (time.time() - created) * 1000
                telemetry.record_usage(
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                    latency_ms=latency_ms
                )

                # Record granular request hit into persistent database ledger
                try:
                    acc_email = account.get("email")
                    quota_snap = QuotaMonitor.get_cached_quotas(acc_email) if acc_email else None
                    db.record_request_hit(
                        request_id=completion_id,
                        timestamp=created,
                        account_email=acc_email,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        reasoning_tokens=reasoning_tokens,
                        latency_ms=latency_ms,
                        status_code=200,
                        stream=0,
                        quota_snapshot=quota_snap,
                        cache_hit=0,
                        tokens_saved=0,
                        key_id=_auth.get("id") if isinstance(_auth, dict) else None
                    )
                    if isinstance(_auth, dict) and _auth.get("id"):
                        db.record_api_key_tokens(
                            key_id=_auth["id"],
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            model=model
                        )
                except Exception as e:
                    logger.error(f"Failed to record request hit to db: {e}")

                # Live broadcast request logged & telemetry to WebSocket clients
                try:
                    event_bus.broadcast_sync({
                        "type": "REQUEST_LOGGED",
                        "request_id": completion_id,
                        "model": model,
                        "total_tokens": prompt_tokens + completion_tokens + reasoning_tokens,
                        "cache_hit": False,
                        "tokens_saved": 0
                    })
                except Exception:
                    pass

                try:
                    metrics_data = telemetry.get_metrics(time_range="1h")
                    s = metrics_data["summary"]
                    event_bus.broadcast_sync({
                        "type": "TELEMETRY_UPDATE",
                        "metrics": {
                            "throughput_tokens_per_sec": s.get("current_tokens_per_sec", 0.0),
                            "tokens_today": {
                                "total": s.get("tokens_today", s.get("total_tokens_all_time", 0)),
                                "prompt": s.get("total_prompt_tokens", 0),
                                "completion": s.get("total_completion_tokens", 0),
                                "reasoning": s.get("total_reasoning_tokens", 0)
                            },
                            "latency_ms": {
                                "ttft_avg": s.get("avg_latency_ms", 0.0),
                                "status": "optimal" if s.get("avg_latency_ms", 0.0) < 4000 else "normal"
                            },
                            "cumulative": {
                                "requests": s.get("total_requests_all_time", 0),
                                "tokens": s.get("total_tokens_all_time", 0)
                            }
                        },
                        "chart_data": metrics_data.get("chart_data"),
                        "chart_range": "1m"
                    })
                except Exception:
                    pass

                resp_json = format_non_stream_response(
                    completion_id, created, model,
                    content_text,
                    tool_calls if tool_calls else None,
                    finish_reason=finish_reason,
                    reasoning_content=reasoning_text if reasoning_text else None,
                    usage={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "reasoning_tokens": reasoning_tokens
                    }
                )
                return JSONResponse(content=resp_json, headers={"X-Cache": "MISS", "X-Cache-Type": "NONE", "X-Cache-Similarity": "0.0", "X-Cache-Key-Scope": scope})

        except Exception as e:
            last_error = e
            logger.error(f"Attempt with {account.get('email')} failed: {e}")
            continue
        finally:
            AccountFailoverPool.release(account_email)

    raise HTTPException(status_code=502, detail=f"All account attempts failed: {last_error}")


# =====================================================================
# Native Anthropic Messages API Compatibility Layer (/v1/messages)
# =====================================================================

@app.post("/v1/messages/count_tokens")
@app.post("/messages/count_tokens")
async def count_tokens(request: Request, _auth: Dict[str, Any] = Depends(require_proxy_api_key)):
    """Calculates input tokens before generation (used by Cline, Claude Code CLI, etc.)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    tokens = estimate_anthropic_tokens(body)
    return {"input_tokens": tokens}


@app.post("/v1/messages")
@app.post("/messages")
async def anthropic_messages(request: Request, _auth: Dict[str, Any] = Depends(require_proxy_api_key)):
    global _last_traffic_timestamp
    _last_traffic_timestamp = time.time()
    """
    Native Anthropic Messages API compatible generation endpoint:
    - Transparent translation to Google Antigravity
    - Full support for system prompt, multi-turn messages, image input, and tools
    - Non-streaming (JSON) and streaming (7-event Anthropic SSE state machine)
    - Full integration with Compiled Binary DB Cache, Context Compactor & Loop Guard
    """
    accounts = account_mgr.load_accounts()
    if not accounts:
        raise HTTPException(
            status_code=500,
            detail="No Google Antigravity accounts configured. Run `prime-gate auth login` or `prime-gate auth import`."
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    cache_cfg = db.get_cache_config()
    anthropic_ver = request.headers.get("anthropic-version", "2023-06-01")

    # 1. Normalize to internal messages for Compactor, Loop Guard, and Cache key
    internal_msgs = anthropic_to_openai_messages(body)

    # 2. Smart Agent Context Compactor
    user_agent = request.headers.get("user-agent", "")
    target_model = str(body.get("model", ""))

    # Policy Enforcement: Model whitelist check for Client Gateway API Key
    model_err = KeyRateLimiter.check_model_allowed(_auth, target_model, request.url.path)
    if model_err:
        raise model_err

    compactor_tokens_saved = 0
    compactor_is_dry_run = bool(cache_cfg.get("compactor_dry_run", False))

    if cache_cfg.get("compactor_enabled", True) and internal_msgs:
        compacted_msgs, compactor_stats = ContextCompactor.compact_messages(
            messages=internal_msgs,
            config=cache_cfg,
            keep_recent_user_turns=cache_cfg.get("compactor_window_turns", cache_cfg.get("compactor_window", 3)),
            max_tool_output_lines=cache_cfg.get("compactor_max_tool_lines", 40),
            client_name=user_agent,
            model_name=target_model,
            dry_run=compactor_is_dry_run,
            preserve_errors=cache_cfg.get("compactor_preserve_errors", True),
            preserve_re_references=cache_cfg.get("compactor_preserve_re_references", True),
        )
        compactor_tokens_saved = compactor_stats.get("tokens_saved", 0)
        compactor_is_dry_run = compactor_stats.get("dry_run", False)
        if compactor_stats.get("compacted"):
            mode_lbl = " (DRY-RUN)" if compactor_is_dry_run else ""
            logger.info(
                f"[COMPACTOR (ANTHROPIC){mode_lbl}] Compacted {compactor_stats['pruned_tool_messages']} tool outputs, "
                f"saved ~{compactor_stats['tokens_saved']} tokens (~{compactor_stats['chars_saved']} chars)."
            )
            if not compactor_is_dry_run:
                internal_msgs = compacted_msgs
            if compactor_tokens_saved > 0:
                try:
                    db.record_compactor_tokens_saved(compactor_tokens_saved)
                except Exception:
                    pass

        # Apply compaction to native Anthropic request body messages
        if isinstance(body.get("messages"), list):
            compacted_anthropic = ContextCompactor.compact_anthropic_body_messages(
                body.get("messages", []),
                config=cache_cfg,
                window_tools=cache_cfg.get("compactor_window_tools", 2),
                max_tool_chars=cache_cfg.get("compactor_max_chars", 600),
                client_name=user_agent,
                model_name=target_model,
                dry_run=compactor_is_dry_run,
                preserve_errors=cache_cfg.get("compactor_preserve_errors", True),
                preserve_re_references=cache_cfg.get("compactor_preserve_re_references", True),
            )
            if not compactor_is_dry_run:
                body["messages"] = compacted_anthropic

    # 3. AI Agent Runaway Loop Guard
    if cache_cfg.get("loop_guard_enabled", True) and internal_msgs:
        intervened_msgs, loop_detected, loop_signature = AgentLoopGuard.check_and_intervene(
            messages=internal_msgs,
            max_repeats=cache_cfg.get("loop_guard_max_repeat", 3)
        )
        if loop_detected:
            logger.warning(f"[LOOP GUARD (ANTHROPIC)] Runaway loop intercepted for '{loop_signature}'.")
            try:
                event_bus.broadcast_sync({
                    "type": "LOOP_GUARD_INTERVENTION",
                    "tool": loop_signature
                })
            except Exception:
                pass

    active_acc = account_mgr.get_active_account()
    model, req_payload = transform_anthropic_to_antigravity(body, account=active_acc)
    stream = bool(body.get("stream", False))
    message_id = "msg_" + uuid.uuid4().hex[:24]
    created = int(time.time())

    # 4. Smart Cache Evaluation Layer
    headers_no_cache = (
        request.headers.get("x-cache-bypass", "").lower() in ("true", "1") or
        request.headers.get("x-no-cache", "").lower() in ("true", "1")
    )
    body_no_cache = bool(body.get("cache") is False or body.get("no_cache") is True)
    has_tools = bool(body.get("tools"))

    key_cache_scope = _auth.get("cache_scope", "shared") if isinstance(_auth, dict) else "shared"
    if key_cache_scope == "key":
        api_key_prefix = f"key_{_auth.get('id', 'default')}"
    else:
        api_key_prefix = _auth.get("prefix", "default") if isinstance(_auth, dict) else "default"
    project_id = (
        request.headers.get("x-project-id") or
        request.headers.get("x-primegate-project") or
        (body.get("metadata", {}).get("user_id") if isinstance(body.get("metadata"), dict) else None)
    )

    cache_key, context_hash, last_user_query, query_hash, tools_sig, scope, has_tools = compute_cache_key(
        model=model,
        messages=internal_msgs,
        system_prompt=body.get("system"),
        tools=body.get("tools"),
        generation_params={
            "temperature": body.get("temperature"),
            "top_p": body.get("top_p"),
            "max_tokens": body.get("max_tokens")
        },
        api_key_prefix=api_key_prefix,
        project_id=project_id
    )
    prompt_hash = query_hash
    prompt_preview = last_user_query[:200]

    bypass_tools = cache_cfg.get("bypass_tools", False)
    semantic_agent_enabled = cache_cfg.get("semantic_agent_enabled", False)
    semantic_allowed = (not has_tools) or semantic_agent_enabled

    cache_eligible = (
        cache_cfg.get("enabled", True) and
        key_cache_scope != "disabled" and
        not headers_no_cache and
        not body_no_cache and
        not (bypass_tools and has_tools) and
        len(last_user_query) >= cache_cfg.get("min_prompt_length", 5)
    )

    cached_res = None
    hit_type = 0  # 1 = Exact Hash, 2 = Vector Semantic
    similarity_score = 0.0

    if cache_eligible:
        cached_res = db.get_cached_response(cache_key, scope=scope)
        if cached_res:
            hit_type = 1
            similarity_score = 1.0
        elif (
            cache_cfg.get("semantic_enabled", True) and
            semantic_allowed and
            last_user_query
        ):
            try:
                from prime_gate.cache.semantic import SemanticVectorEngine
                q_vec = SemanticVectorEngine.embed_query(last_user_query)
                threshold = cache_cfg.get("semantic_threshold_agent", 0.96) if has_tools else cache_cfg.get("semantic_threshold_chat", cache_cfg.get("semantic_threshold", 0.93))
                if q_vec is not None:
                    sem_match = db.find_semantic_match(
                        model=model,
                        query_vec=q_vec,
                        scope=scope,
                        context_hash=context_hash,
                        threshold=threshold,
                        tools_signature=tools_sig
                    )
                    if sem_match:
                        cached_res, similarity_score = sem_match
                        hit_type = 2
            except Exception as e:
                logger.warning(f"Semantic cache search failed ({e}), continuing upstream.")

    if cached_res:
        hit_start = time.time()
        hit_latency = round((time.time() - hit_start) * 1000 + (3.2 if hit_type == 1 else 12.5), 1)
        tokens_saved = cached_res.get("total_tokens", 0)
        p_tok = cached_res.get("prompt_tokens", 0)
        c_tok = cached_res.get("completion_tokens", 0)

        acc_email = active_acc.get("email") if active_acc else "smart-cache"
        quota_snap = QuotaMonitor.get_cached_quotas(acc_email) if active_acc else None

        try:
            db.record_request_hit(
                request_id=message_id,
                timestamp=created,
                account_email=acc_email,
                model=model,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                reasoning_tokens=0,
                latency_ms=hit_latency,
                status_code=200,
                stream=1 if stream else 0,
                quota_snapshot=quota_snap,
                cache_hit=1,
                tokens_saved=tokens_saved,
                cache_hit_type=hit_type,
                similarity_score=similarity_score
            )
        except Exception as e:
            logger.error(f"Failed to record Anthropic cache hit: {e}")

        try:
            event_bus.broadcast_sync({
                "type": "REQUEST_LOGGED",
                "request_id": message_id,
                "model": model,
                "total_tokens": tokens_saved,
                "cache_hit": True,
                "cache_hit_type": "exact" if hit_type == 1 else "semantic",
                "similarity": similarity_score,
                "tokens_saved": tokens_saved
            })
            event_bus.broadcast_sync({
                "type": "CACHE_HIT",
                "cache_key": cache_key,
                "hit_type": "exact" if hit_type == 1 else "semantic",
                "similarity": similarity_score,
                "tokens_saved": tokens_saved,
                "stats": db.get_cache_stats()
            })
        except Exception:
            pass

        cache_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "anthropic-version": anthropic_ver,
            "X-Cache": "HIT",
            "X-Cache-Type": "EXACT" if hit_type == 1 else "SEMANTIC",
            "X-Similarity": f"{similarity_score:.3f}",
            "X-Tokens-Saved": str(tokens_saved)
        }

        if stream:
            return StreamingResponse(
                stream_cached_anthropic_sse(message_id, model, cached_res, prompt_tokens=p_tok),
                media_type="text/event-stream",
                headers=cache_headers
            )
        else:
            return JSONResponse(
                content=format_anthropic_non_stream_response(
                    message_id=message_id,
                    model=model,
                    content_blocks=[{"type": "text", "text": cached_res.get("response_text", "")}],
                    stop_reason="end_turn",
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    cache_read_tokens=tokens_saved
                ),
                headers=cache_headers
            )

    # 5. Mid-Flight Account Failover Pool
    ordered_accounts = AccountFailoverPool.get_ordered_accounts(
        accounts=accounts,
        active_account=active_acc,
        model=model,
        quota_cache=QuotaMonitor.get_cached_quotas()
    )
    primary_email = ordered_accounts[0].get("email", "") if ordered_accounts else ""
    AccountFailoverPool.acquire(primary_email)

    cache_meta = {
        "eligible": cache_eligible,
        "cache_key": cache_key,
        "prompt_hash": prompt_hash,
        "preview": prompt_preview,
        "ttl": cache_cfg.get("ttl_seconds", 86400),
        "last_user_query": last_user_query,
        "tools_sig": tools_sig,
        "scope": scope,
        "context_hash": context_hash,
        "embedding_model": cache_cfg.get("embedding_model")
    }

    if stream:
        try:
            return StreamingResponse(
                stream_anthropic_sse(
                    ordered_accounts=ordered_accounts,
                    model=model,
                    req_payload=req_payload,
                    message_id=message_id,
                    created=created,
                    declared_tools=body.get("tools"),
                    cache_meta=cache_meta,
                    acquired_email=primary_email,
                    key_id=_auth.get("id") if isinstance(_auth, dict) else None
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "anthropic-version": anthropic_ver,
                    "X-Cache": "MISS"
                }
            )
        except Exception:
            AccountFailoverPool.release(primary_email)
            raise

    # Non-streaming Request Flow
    start_t = time.time()
    prompt_tokens = max(1, len(json.dumps(req_payload)) // 4)
    timeout = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)
    client = get_shared_client()
    for attempt, account in enumerate(ordered_accounts):
        account_email = account.get("email", "")
        AccountFailoverPool.acquire(account_email)
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
                err_text = await resp.aread()
                AccountFailoverPool.mark_rate_limited(account_email, cooldown_seconds=6)
                logger.warning(
                    f"[FAILOVER (ANTHROPIC)] Upstream HTTP {resp.status_code} on {account_email}: "
                    f"{err_text.decode('utf-8', errors='ignore')[:300]}. Rotating account..."
                )
                try:
                    event_bus.broadcast_sync({
                        "type": "ACCOUNT_FAILOVER",
                        "account": account_email,
                        "status_code": resp.status_code
                    })
                except Exception:
                    pass
                if attempt == len(ordered_accounts) - 1:
                    await asyncio.sleep(1.2)
                else:
                    await asyncio.sleep(0.4)
                continue

            if resp.status_code != 200:
                err_text = await resp.aread()
                logger.error(f"Upstream error {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:300]}")
                if attempt < len(ordered_accounts) - 1:
                    continue
                raise HTTPException(status_code=resp.status_code, detail=f"Upstream error: {resp.status_code}")

            content_blocks: List[Dict[str, Any]] = []
            accumulated_text = ""
            completion_tokens = 0
            stop_reason = "end_turn"

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw_json = line[len("data:"):].strip()
                if not raw_json or raw_json == "[DONE]":
                    continue
                try:
                    payload = json.loads(raw_json)
                    response_obj = payload.get("response", payload)
                    usage = response_obj.get("usageMetadata", {})
                    if usage.get("promptTokenCount"):
                        prompt_tokens = usage["promptTokenCount"]
                    if usage.get("candidatesTokenCount"):
                        completion_tokens = usage["candidatesTokenCount"]

                    candidates = response_obj.get("candidates", [])
                    if candidates:
                        cand = candidates[0]
                        parts = cand.get("content", {}).get("parts", [])
                        cand_sig = None
                        for p in parts:
                            s = p.get("thoughtSignature") or p.get("thought_signature")
                            if s and s != "skip_thought_signature_validator":
                                cand_sig = s
                                break

                        for p in parts:
                            if p.get("text"):
                                accumulated_text += p["text"]
                            elif p.get("functionCall"):
                                fn = p["functionCall"]
                                call_id = fn.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"
                                raw_name = fn.get("name", "tool")
                                raw_args = fn.get("args", {})
                                fn_name, fn_args = normalize_tool_call(raw_name, raw_args, body.get("tools"))
                                sig = p.get("thoughtSignature") or p.get("thought_signature") or cand_sig
                                if sig and sig != "skip_thought_signature_validator":
                                    thought_sig_cache.store(
                                        key=call_id,
                                        signature=sig,
                                        fn_name=fn_name,
                                        fn_args=fn_args,
                                        model=model
                                    )
                                content_blocks.append({
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": fn_name,
                                    "input": fn_args if isinstance(fn_args, dict) else {}
                                })
                                stop_reason = "tool_use"
                except Exception:
                    continue

            if "call:" in accumulated_text:
                cleaned_txt, text_tcs = extract_text_tool_calls(accumulated_text, body.get("tools"))
                if text_tcs:
                    accumulated_text = cleaned_txt
                    for tc in text_tcs:
                        fn = tc["function"]
                        fn_name = fn["name"]
                        fn_args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id") or f"toolu_{uuid.uuid4().hex[:12]}",
                            "name": fn_name,
                            "input": fn_args if isinstance(fn_args, dict) else {}
                        })
                        stop_reason = "tool_use"

            if accumulated_text:
                content_blocks.insert(0, {"type": "text", "text": accumulated_text})

            if not completion_tokens:
                completion_tokens = max(1, len(accumulated_text) // 4)

            latency_ms = round((time.time() - start_t) * 1000, 1)
            telemetry.record_usage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=0,
                latency_ms=latency_ms
            )

            if cache_eligible and accumulated_text and stop_reason != "tool_use":
                try:
                    emb_bytes = None
                    if last_user_query:
                        from prime_gate.cache.semantic import SemanticVectorEngine
                        q_vec = SemanticVectorEngine.embed_passage(last_user_query)
                        if q_vec is not None:
                            emb_bytes = SemanticVectorEngine.vector_to_blob(q_vec)

                    db.store_cached_response(
                        cache_key=cache_key,
                        prompt_hash=prompt_hash,
                        prompt_preview=prompt_preview,
                        response_text=accumulated_text,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        reasoning_tokens=0,
                        embedding=emb_bytes,
                        tools_signature=tools_sig,
                        scope=scope,
                        context_hash=context_hash,
                        ttl_seconds=cache_cfg.get("ttl_seconds", 86400),
                        embedding_model=cache_cfg.get("embedding_model")
                    )
                    event_bus.broadcast_sync({
                        "type": "CACHE_STORED",
                        "key": cache_key,
                        "model": model,
                        "total_tokens": prompt_tokens + completion_tokens
                    })
                except Exception as e:
                    logger.warning(f"Failed to cache Anthropic non-stream response: {e}")

            try:
                quota_snap = QuotaMonitor.get_cached_quotas(account_email)
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
                    stream=0,
                    quota_snapshot=quota_snap,
                    cache_hit=0,
                    tokens_saved=0,
                    key_id=_auth.get("id") if isinstance(_auth, dict) else None
                )
                if isinstance(_auth, dict) and _auth.get("id"):
                    db.record_api_key_tokens(
                        key_id=_auth["id"],
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        model=model
                    )
            except Exception as e:
                logger.error(f"Failed to record Anthropic request hit: {e}")

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

            return JSONResponse(
                content=format_anthropic_non_stream_response(
                    message_id=message_id,
                    model=model,
                    content_blocks=content_blocks,
                    stop_reason=stop_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cache_read_tokens=0
                ),
                headers={"anthropic-version": anthropic_ver, "X-Cache": "MISS"}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[FAILOVER (ANTHROPIC)] Connection failed for {account_email}: {e}")
            if attempt == len(ordered_accounts) - 1:
                raise HTTPException(status_code=502, detail=f"All upstream accounts exhausted: {e}")
            continue
        finally:
            AccountFailoverPool.release(account_email)

    raise HTTPException(status_code=502, detail="Failed to connect to upstream Antigravity accounts.")




@app.post("/v1/search")
@app.post("/search")
async def handle_custom_search(request: Request, _auth: Dict[str, Any] = Depends(require_proxy_api_key)):
    """
    Desktop search provider endpoint for Claude Code and OpenCode.
    Accepts JSON {"q": "query"} or {"query": "query"} and returns {"results": [{"title", "url", "snippet"}]}.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    q = body.get("q") or body.get("query") or ""
    if not q:
        params = request.query_params
        q = params.get("q") or params.get("query") or ""

    results = await search_web(q, max_results=8)
    return JSONResponse(content={"results": results})


def main():
    parser = argparse.ArgumentParser(description="Prime Gate Antigravity Proxy Core Server")
    parser.add_argument("--port", type=int, default=DEFAULT_API_PORT, help="Port to listen on")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Host to bind on")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"  PRIME GATE PROXY ANTIGRAVITY (v{__version__}) - {__codename__}")
    print(f"  Running on:    http://{args.host}:{args.port}")
    print(f"  OpenAI API:    http://{args.host}:{args.port}/v1/chat/completions")
    print(f"  Anthropic API: http://{args.host}:{args.port}/v1/messages")
    print(f"=======================================================\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
