import os
import sys
import time
import json
import uuid
import logging
import argparse
from typing import Dict, Any, List, Optional, AsyncGenerator

import httpx
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from . import __version__, __codename__
from .config import (
    DEFAULT_HOST, DEFAULT_API_PORT, ANTIGRAVITY_ENDPOINT,
    MODELS_CATALOG
)
from .auth import AccountManager, get_access_token
from .quota import QuotaMonitor
from .translator import (
    transform_openai_to_antigravity,
    format_sse_chunk,
    format_non_stream_response
)
from .db import db, event_bus, WebSocketLogHandler
from .db.sentinel import sentinel
from .telemetry import telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("prime_gate.server")

# Connect Python logging directly to WebSocket real-time broadcast
ws_handler = WebSocketLogHandler(event_bus)
ws_handler.setLevel(logging.INFO)
ws_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(ws_handler)

app = FastAPI(
    title="Prime Gate Antigravity Proxy",
    version=__version__,
    description="High-performance OpenAI-compatible gateway for Google Antigravity"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

account_mgr = AccountManager()
START_TIME = time.time()

@app.on_event("startup")
async def on_startup():
    import asyncio
    event_bus.set_loop(asyncio.get_running_loop())
    await sentinel.start()
    logger.info("Prime Gate Engine active with Compiled Binary Database (WAL Mode + CRC32 Sentinel)")

    # Auto-load models & verify quota on daemon startup if user is logged in
    active_acc = account_mgr.get_active_account()
    if active_acc:
        email = active_acc.get("email")
        logger.info(f"Active account detected ({email}). Auto-syncing live Antigravity models and quota on daemon start...")

        async def _startup_sync():
            try:
                models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=True)
                quota = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=True)
                logger.info(f"[STARTUP SYNC] Successfully loaded {len(models)} live models and {len(quota)} quota buckets into binary DB for {email}.")
            except Exception as e:
                logger.warning(f"[STARTUP SYNC] Startup sync deferred (will use binary DB cached models): {e}")

        asyncio.create_task(_startup_sync())

@app.on_event("shutdown")
async def on_shutdown():
    await sentinel.stop()
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
            "status": "/api/status"
        }
    }

@app.get("/v1/health")
@app.get("/health")
async def v1_health_check(
    limit: int = 50,
    level: Optional[str] = None,
    refresh: bool = False
):
    """
    Comprehensive gateway health & telemetry endpoint:
    - Live health and operational status of all supported models
    - Real-time quota allocations and bucket reset timelines
    - Compiled binary database state and integrity verification
    - In-memory token telemetry KPIs and throughput
    - Structured chronological log history of gateway and upstream API events
    """
    now = time.time()
    active_acc = account_mgr.get_active_account()
    accounts = account_mgr.load_accounts()

    # 1. Evaluate Model Health across all models
    models_health = await QuotaMonitor.get_models_health(active_acc, force_refresh=refresh)

    # 2. Quota telemetry
    if active_acc:
        quota_summary = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=refresh)
        tier_label = QuotaMonitor.get_tier_label(active_acc)
    else:
        quota_summary = []
        tier_label = "Unauthenticated"

    # 3. Database status & integrity
    db_status = db.get_status()

    # 4. Telemetry metrics snapshot
    metrics = telemetry.get_metrics(time_range="minute")
    telemetry_summary = metrics.get("summary", {})

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
        "uptime_seconds": int(now - START_TIME),
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
        }
    }

@app.get("/v1/models")
@app.get("/models")
async def list_models(refresh: bool = False):
    """OpenAI standard models list endpoint dynamically resolved from Antigravity."""
    active_acc = account_mgr.get_active_account()
    if active_acc:
        models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=refresh)
    else:
        models = QuotaMonitor.get_available_models(None)
    now = int(time.time())

    data = [
        {
            "id": m["id"],
            "object": "model",
            "created": now,
            "owned_by": m.get("owned_by", "google-antigravity"),
            "permission": [],
            "root": m["id"],
            "parent": None
        }
        for m in models
    ]
    return {"object": "list", "data": data}

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

@app.post("/api/models/refresh")
async def api_models_refresh():
    """Forces refreshing live models and quota from Google Antigravity account."""
    active_acc = account_mgr.get_active_account()
    if not active_acc:
        return {"success": False, "error": "No active account configured"}
    models = await QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=True)
    quota = await QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=True)
    return {
        "success": True,
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

        # Immediately fetch live models and quota from Antigravity and save to binary database
        models = await QuotaMonitor.fetch_live_models_from_antigravity(new_account, force_refresh=True)
        quota = await QuotaMonitor.fetch_live_quota_from_antigravity(new_account, force_refresh=True)
        logger.info(f"First login: Successfully saved {len(models)} live models and {len(quota)} quota buckets into binary DB for {new_account.get('email')}.")

        return {
            "success": True,
            "account": new_account.get("email"),
            "models_count": len(models),
            "quota_count": len(quota)
        }
    except Exception as e:
        logger.error(f"OAuth login failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.get("/api/accounts")
async def api_accounts_list():
    """List all accounts currently configured in Prime Gate."""
    accounts = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()
    return {
        "accounts": [
            {
                "email": a.get("email"),
                "projectId": a.get("projectId"),
                "is_active": a.get("email") == (active_acc.get("email") if active_acc else None),
                "tier": QuotaMonitor.get_tier_label(a)
            }
            for a in accounts
        ],
        "total": len(accounts)
    }

@app.post("/api/auth/remove")
@app.post("/api/auth/delete")
async def api_auth_remove(request: Request):
    """Remove an account by email from Prime Gate."""
    try:
        body = await request.json()
        email = body.get("email", "")
    except Exception:
        email = ""
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    success = account_mgr.remove_account(email)
    remaining = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()
    return {
        "success": success,
        "removed": email,
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
async def api_db_check():
    """Triggers deep SQLite B-Tree and record-level CRC32 integrity audit."""
    return db.run_integrity_check()

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

@app.get("/api/metrics/tokens")
async def api_token_metrics(range: str = "minute"):
    """Returns token consumption time-series chart data and KPIs (second, minute, hour, day)."""
    if range not in ["second", "minute", "hour", "day"]:
        range = "minute"
    return telemetry.get_metrics(time_range=range)

async def stream_antigravity_sse(
    upstream_url: str,
    headers: Dict[str, str],
    wrapped_body: Dict[str, Any],
    completion_id: str,
    created: int,
    model: str
) -> AsyncGenerator[str, None]:
    """Stream SSE chunks from Google Antigravity and yield OpenAI SSE format chunks."""
    start_t = time.time()
    prompt_tokens = max(1, len(json.dumps(wrapped_body.get("request", {}))) // 4)
    completion_tokens = 0
    reasoning_tokens = 0

    timeout = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", upstream_url, headers=headers, json=wrapped_body) as resp:
            if resp.status_code != 200:
                err_text = await resp.aread()
                logger.error(f"Upstream stream error {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:300]}")
                yield f"data: {json.dumps({'error': {'message': f'Upstream error: {resp.status_code}'}})}\n\n"
                yield "data: [DONE]\n\n"
                return

            has_emitted_tool_call = False
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                raw_json = line[len("data:"):].strip()
                if not raw_json or raw_json == "[DONE]":
                    continue

                try:
                    payload = json.loads(raw_json)
                    response_obj = payload.get("response", payload)
                    candidates = response_obj.get("candidates", [])
                    if not candidates:
                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if part.get("thought") and part.get("text"):
                            reasoning_tokens += max(1, len(part["text"].split()))
                            yield format_sse_chunk(
                                completion_id, created, model,
                                {"reasoning_content": part["text"]}
                            )
                        elif part.get("text"):
                            completion_tokens += max(1, len(part["text"].split()))
                            yield format_sse_chunk(
                                completion_id, created, model,
                                {"content": part["text"]}
                            )
                        elif part.get("functionCall"):
                            has_emitted_tool_call = True
                            call_id = "call_" + uuid.uuid4().hex[:8]
                            fn_call = part["functionCall"]
                            yield format_sse_chunk(
                                completion_id, created, model,
                                {
                                    "tool_calls": [{
                                        "index": 0,
                                        "id": call_id,
                                        "type": "function",
                                        "function": {
                                            "name": fn_call.get("name"),
                                            "arguments": json.dumps(fn_call.get("args", {}))
                                        }
                                    }]
                                }
                            )
                except Exception:
                    continue

            # Record telemetry for completed stream
            latency_ms = (time.time() - start_t) * 1000
            telemetry.record_usage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                latency_ms=latency_ms
            )

            # Send final stop chunk
            finish_reason = "tool_calls" if has_emitted_tool_call else "stop"
            yield format_sse_chunk(completion_id, created, model, {}, finish_reason=finish_reason)
            yield "data: [DONE]\n\n"

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request):
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

    model, req_payload = transform_openai_to_antigravity(body)
    stream = bool(body.get("stream", False))
    completion_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())

    # Try active accounts with failover
    last_error = None
    for attempt in range(len(accounts)):
        account = accounts[attempt]
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

            upstream_url = (
                f"{ANTIGRAVITY_ENDPOINT}/v1internal:"
                f"{'streamGenerateContent?alt=sse' if stream else 'generateContent'}"
            )

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "antigravity/1.18.3",
                "Accept": "text/event-stream" if stream else "application/json"
            }

            if stream:
                return StreamingResponse(
                    stream_antigravity_sse(
                        upstream_url, headers, wrapped_body,
                        completion_id, created, model
                    ),
                    media_type="text/event-stream"
                )
            else:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(upstream_url, headers=headers, json=wrapped_body)
                    if resp.status_code == 429:
                        logger.warning(f"Account {account.get('email')} quota exceeded. Trying next...")
                        continue

                    if resp.status_code != 200:
                        raise HTTPException(status_code=resp.status_code, detail=resp.text)

                    payload = resp.json()
                    response_obj = payload.get("response", payload)
                    candidates = response_obj.get("candidates", [])
                    content_text = ""
                    tool_calls = []

                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            if p.get("text"):
                                content_text += p["text"]
                            if p.get("functionCall"):
                                fn = p["functionCall"]
                                tool_calls.append({
                                    "id": "call_" + uuid.uuid4().hex[:8],
                                    "type": "function",
                                    "function": {
                                        "name": fn.get("name"),
                                        "arguments": json.dumps(fn.get("args", {}))
                                    }
                                })

                    latency_ms = (time.time() - created) * 1000
                    p_toks = max(1, len(json.dumps(req_payload)) // 4)
                    c_toks = max(1, len(content_text.split()))
                    telemetry.record_usage(
                        model=model,
                        prompt_tokens=p_toks,
                        completion_tokens=c_toks,
                        reasoning_tokens=0,
                        latency_ms=latency_ms
                    )

                    return format_non_stream_response(
                        completion_id, created, model,
                        content_text, tool_calls if tool_calls else None
                    )

        except Exception as e:
            last_error = e
            logger.error(f"Attempt with {account.get('email')} failed: {e}")
            continue

    raise HTTPException(status_code=502, detail=f"All account attempts failed: {last_error}")

def main():
    parser = argparse.ArgumentParser(description="Prime Gate Antigravity Proxy Core Server")
    parser.add_argument("--port", type=int, default=DEFAULT_API_PORT, help="Port to listen on")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Host to bind on")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"  PRIME GATE PROXY ANTIGRAVITY (v{__version__}) - {__codename__}")
    print(f"  Running on: http://{args.host}:{args.port}")
    print(f"  OpenAI API: http://{args.host}:{args.port}/v1")
    print(f"=======================================================\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
