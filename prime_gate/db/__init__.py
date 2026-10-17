"""
Prime Gate Compiled Binary Database Module
Provides compiled C binary storage (SQLite WAL + Sealed BLOBs),
record-level CRC32 checksums, real-time WebSocket event dispatching,
and instant database corruption telemetry.
"""

from .binary_codec import (
    BinaryCodec, DatabaseCorruptedError,
    REC_ACCOUNT, REC_MODEL, REC_QUOTA, REC_SYSTEM, REC_LOG
)
from .engine import BinaryDatabaseEngine, db
from .events import DBEventBus, WebSocketLogHandler, event_bus

__all__ = [
    "BinaryCodec",
    "DatabaseCorruptedError",
    "BinaryDatabaseEngine",
    "db",
    "DBEventBus",
    "WebSocketLogHandler",
    "event_bus",
    "REC_ACCOUNT",
    "REC_MODEL",
    "REC_QUOTA",
    "REC_SYSTEM",
    "REC_LOG"
]
