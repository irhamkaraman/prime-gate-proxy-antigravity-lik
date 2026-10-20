"""
Prime Gate High-Performance Persistent HTTP Connection Pool.
Maintains reusable HTTP/1.1 TCP connections to Google Antigravity & OAuth endpoints.
Eliminates ephemeral socket churn and Windows TIME_WAIT socket exhaustion.
"""

import httpx
import logging
from typing import Optional

logger = logging.getLogger("prime_gate.client_pool")

_shared_async_client: Optional[httpx.AsyncClient] = None

def get_shared_client() -> httpx.AsyncClient:
    """
    Returns a global singleton httpx.AsyncClient with persistent connection pooling.
    Configured with generous read timeouts (240s) for large prompts (50k+ tokens)
    and deep reasoning generation.
    """
    global _shared_async_client
    if _shared_async_client is None or _shared_async_client.is_closed:
        limits = httpx.Limits(
            max_keepalive_connections=50,
            max_connections=150,
            keepalive_expiry=120.0
        )
        timeout = httpx.Timeout(
            connect=15.0,
            read=240.0,  # 4 minutes: ample room for 60k+ token prompts and deep reasoning
            write=30.0,
            pool=30.0
        )
        _shared_async_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            http2=False
        )
        logger.info("[CLIENT_POOL] Initialized persistent HTTP connection pool (keepalive: 120s, read_timeout: 240s)")
    return _shared_async_client

async def close_shared_client():
    """Cleanly close the shared connection pool during application shutdown."""
    global _shared_async_client
    if _shared_async_client and not _shared_async_client.is_closed:
        try:
            await _shared_async_client.aclose()
            logger.info("[CLIENT_POOL] Closed persistent HTTP connection pool")
        except Exception as e:
            logger.warning(f"[CLIENT_POOL] Error closing connection pool: {e}")
        _shared_async_client = None
