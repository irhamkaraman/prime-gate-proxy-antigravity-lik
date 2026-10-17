import asyncio
import logging
import time
from typing import Set, Dict, Any, Optional

try:
    from fastapi import WebSocket
except ImportError:
    WebSocket = Any

logger = logging.getLogger("prime_gate.db.events")

class DBEventBus:
    """
    Central real-time event dispatcher for Prime Gate Database and Proxy runtime.
    Maintains active WebSocket subscriber pools and dispatches streaming telemetry,
    database mutation events, log lines, and critical corruption alerts.
    """

    def __init__(self):
        self._subscribers: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def register(self, ws: WebSocket):
        self._subscribers.add(ws)
        logger.info(f"WebSocket client registered. Active subscribers: {len(self._subscribers)}")

    def unregister(self, ws: WebSocket):
        self._subscribers.discard(ws)
        logger.info(f"WebSocket client disconnected. Active subscribers: {len(self._subscribers)}")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def broadcast(self, event: Dict[str, Any]):
        """Asynchronously send event dictionary to all active WebSocket clients."""
        if not self._subscribers:
            return

        dead_connections = set()
        for ws in list(self._subscribers):
            try:
                await ws.send_json(event)
            except Exception:
                dead_connections.add(ws)

        for dead in dead_connections:
            self._subscribers.discard(dead)

    def dispatch_sync(self, event: Dict[str, Any]):
        """Dispatches an event from synchronous code into the running asyncio event loop."""
        try:
            loop = self._loop
            if loop is None or not loop.is_running():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(event), loop)
        except Exception as e:
            # Prevent logging errors inside log handler
            pass

    def notify_corruption(self, key: str, reason: str, details: Optional[Dict[str, Any]] = None):
        """Immediately broadcast a CRITICAL database corruption notification."""
        payload = {
            "type": "DB_CORRUPTED",
            "severity": "CRITICAL",
            "timestamp": time.time(),
            "key": key,
            "reason": reason,
            "details": details or {},
            "recommendation": "Database Sentinel will isolate corrupted block or fallback to snapshot."
        }
        self.dispatch_sync(payload)

    def notify_mutation(self, action: str, key: str, record_type: int):
        """Broadcast a record mutation event (insert, update, delete)."""
        payload = {
            "type": "DB_MUTATION",
            "action": action,
            "key": key,
            "record_type": record_type,
            "timestamp": time.time()
        }
        self.dispatch_sync(payload)

    def notify_health(self, status: str, size_bytes: int, record_count: int, integrity_ok: bool):
        """Broadcast periodic database health snapshot."""
        payload = {
            "type": "DB_HEALTH",
            "status": status,
            "size_bytes": size_bytes,
            "record_count": record_count,
            "integrity_ok": integrity_ok,
            "timestamp": time.time()
        }
        self.dispatch_sync(payload)


# Global Singleton Event Bus
event_bus = DBEventBus()


class WebSocketLogHandler(logging.Handler):
    """
    Python logging handler that streams log records directly to connected
    WebSocket clients in real-time, connecting stdout/stderr and internal logs.
    """

    def __init__(self, bus: DBEventBus = event_bus):
        super().__init__()
        self.bus = bus

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            payload = {
                "type": "LOG_ENTRY",
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
                "created": record.created,
                "is_corrupt_alert": "CORRUPT" in msg.upper() or "CORRUPTED" in msg.upper()
            }
            self.bus.dispatch_sync(payload)
        except Exception:
            self.handleError(record)
