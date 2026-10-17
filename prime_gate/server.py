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

@app.on_event("shutdown")
async def on_shutdown():
    await sentinel.stop()
    db.close()

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "prime-gate-proxy-antigravity-lik",
        "version": __version__,
        "codename": __codename__,
        "uptime_seconds": int(time.time() - START_TIME)
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
    """Import accounts from local OpenCode configuration."""
    count = account_mgr.import_from_opencode()
    accounts = account_mgr.load_accounts()
    active_acc = account_mgr.get_active_account()
    return {
        "success": count > 0,
        "imported": count,
        "total_accounts": len(accounts),
        "active_account": active_acc.get("email") if active_acc else None
    }

@app.post("/api/auth/login")
async def api_auth_login():
    """Trigger interactive Google OAuth PKCE login via browser."""
    import asyncio
    from .auth import start_interactive_login
    try:
        new_account = await asyncio.to_thread(start_interactive_login)
        accounts = account_mgr.load_accounts()
        accounts = [a for a in accounts if a.get("email") != new_account["email"]]
        accounts.append(new_account)
        account_mgr.save_accounts(accounts)
        return {"success": True, "account": new_account.get("email")}
    except Exception as e:
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



async def stream_antigravity_sse(
    upstream_url: str,
    headers: Dict[str, str],
    wrapped_body: Dict[str, Any],
    completion_id: str,
    created: int,
    model: str
) -> AsyncGenerator[str, None]:
    """Stream SSE chunks from Google Antigravity and yield OpenAI SSE format chunks."""
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
                            yield format_sse_chunk(
                                completion_id, created, model,
                                {"reasoning_content": part["text"]}
                            )
                        elif part.get("text"):
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
