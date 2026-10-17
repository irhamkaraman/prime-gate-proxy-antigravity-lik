import asyncio
import logging
import time
from typing import Optional

from .engine import db, BinaryDatabaseEngine
from .events import event_bus

logger = logging.getLogger("prime_gate.db.sentinel")

class DatabaseSentinel:
    """
    Background Watchdog Daemon that continuously audits database health,
    monitors binary CRC32 checksums, and coordinates automatic incident recovery.
    """

    def __init__(self, engine: BinaryDatabaseEngine = db, check_interval_seconds: int = 45):
        self.engine = engine
        self.interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Starts the background sentinel loop in an asyncio event loop."""
        if self._running:
            return
        self._running = True
        logger.info(f"Database Sentinel Daemon activated (Audit interval: {self.interval}s)")
        self._task = asyncio.create_task(self._audit_loop())

    async def stop(self):
        """Stops the background sentinel loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Database Sentinel Daemon stopped.")

    async def _audit_loop(self):
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                result = self.engine.run_integrity_check()
                if not result["healthy"]:
                    logger.critical(
                        f"[CRITICAL] [SENTINEL ALERT] Database integrity audit failed! "
                        f"{result['corruptions_count']} corrupted record(s) detected!"
                    )
                else:
                    logger.debug(
                        f"Database Sentinel audit passed: {result['records_scanned']} records verified, "
                        f"size: {result['size_bytes']} bytes."
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Database Sentinel audit loop: {e}")


sentinel = DatabaseSentinel()
