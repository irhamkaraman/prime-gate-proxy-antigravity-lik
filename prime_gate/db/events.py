import asyncio
import logging
import time
import collections
import threading
from typing import Set, Dict, Any, Optional, List

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
    Also retains a thread-safe ring buffer of recent structured logs for REST API inspection.
    """

    def __init__(self):
        self._subscribers: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._log_history: collections.deque = collections.deque(maxlen=500)
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def add_log(self, entry: Dict[str, Any]):
        """Append a structured log entry into the circular buffer in a thread-safe manner."""
        with self._lock:
            self._log_history.append(entry)

    def get_recent_logs(self, limit: int = 50, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns recent structured log entries (newest first).
        Optional level filter: DEBUG, INFO, WARNING, ERROR, CRITICAL.
        """
        with self._lock:
            items = list(self._log_history)

        if level:
            lvl = level.upper().strip()
            level_hierarchy = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "WARN": 30, "ERROR": 40, "CRITICAL": 50}
            min_val = level_hierarchy.get(lvl, 20)
            items = [item for item in items if level_hierarchy.get(item.get("level", "INFO").upper(), 20) >= min_val]

        items.reverse()  # Newest first
        return items[:limit]

    @property
    def total_logs_buffered(self) -> int:
        with self._lock:
            return len(self._log_history)

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
            created_epoch = record.created
            is_corrupt = "CORRUPT" in msg.upper() or "CORRUPTED" in msg.upper()
            is_error = record.levelno >= logging.ERROR

            log_entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_epoch)),
                "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created_epoch)),
                "epoch": round(created_epoch, 3),
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
                "is_error": is_error,
                "is_corrupt_alert": is_corrupt
            }

            # Buffer locally for REST API health inspection
            self.bus.add_log(log_entry)

            # Broadcast live to WebSocket clients
            payload = {
                "type": "LOG_ENTRY",
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
                "created": created_epoch,
                "is_corrupt_alert": is_corrupt
            }
            self.bus.dispatch_sync(payload)
        except Exception:
            self.handleError(record)
