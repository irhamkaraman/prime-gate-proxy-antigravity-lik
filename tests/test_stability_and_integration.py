import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock
from prime_gate.resilience import AccountFailoverPool
from prime_gate.translator.thought_cache import ThoughtSignatureCache
from prime_gate.db.engine import BinaryDatabaseEngine

class TestStabilityAndIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        AccountFailoverPool._cooldowns.clear()
        AccountFailoverPool._in_flight.clear()

    def test_failover_on_429_503_and_cooldown_recovery(self):
        """Simulates 429 rate limit failover and verifies cooldown expiry recovery."""
        accounts = [
            {"email": "primary@example.com", "name": "Primary Account"},
            {"email": "secondary@example.com", "name": "Secondary Account"}
        ]
        # 1. Primary receives 429 rate limit
        AccountFailoverPool.mark_rate_limited("primary@example.com", cooldown_seconds=0.05)
        
        # 2. Proxy selects failover account
        selected = AccountFailoverPool.get_failover_account("primary@example.com", accounts)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["email"], "secondary@example.com")
        
        # 3. Wait for cooldown expiration
        time.sleep(0.06)
        self.assertTrue(AccountFailoverPool.is_available({"email": "primary@example.com"}))

    def test_all_accounts_exhausted_returns_clear_status(self):
        """Verifies clean failure selection when all accounts are rate-limited (no infinite hang)."""
        accounts = [
            {"email": "acc1@example.com"},
            {"email": "acc2@example.com"}
        ]
        AccountFailoverPool.mark_rate_limited("acc1@example.com", cooldown_seconds=60)
        AccountFailoverPool.mark_rate_limited("acc2@example.com", cooldown_seconds=60)

        # Neither account is available
        self.assertFalse(AccountFailoverPool.is_available(accounts[0]))
        self.assertFalse(AccountFailoverPool.is_available(accounts[1]))

        # With allow_cooling_fallback=False, selection returns None cleanly
        next_acc = AccountFailoverPool.get_failover_account("acc1@example.com", accounts, allow_cooling_fallback=False)
        self.assertIsNone(next_acc)

        # When only 1 account exists and it fails, get_failover_account returns None
        single_account = [{"email": "solo@example.com"}]
        AccountFailoverPool.mark_rate_limited("solo@example.com", cooldown_seconds=60)
        self.assertIsNone(AccountFailoverPool.get_failover_account("solo@example.com", single_account))

    def test_gemini3_thought_signature_cache_multi_turn(self):
        """Verifies ThoughtSignatureCache preserves signature across tool calling turns."""
        cache = ThoughtSignatureCache(maxsize=100, ttl_seconds=2)
        call_id = "call_gemini3_reasoning_123"
        tool_name = "execute_code"
        raw_sig = "EAEaGVNlY3JldFRob3VnaHRTaWduYXR1cmUxMjM="

        # Store signature
        cache.store(call_id, raw_sig)
        cache.store(tool_name, raw_sig)

        # Retrieve signature
        self.assertEqual(cache.get(call_id), raw_sig)
        self.assertEqual(cache.get(tool_name), raw_sig)

        # Non-existent key returns None
        self.assertIsNone(cache.get("non_existent_key"))

        # Wait for TTL expiration
        time.sleep(2.05)
        self.assertIsNone(cache.get(call_id))
        from prime_gate.db import db
        db.clean_expired_thought_signatures()

    def test_db_migration_idempotent_multi_run(self):
        """Verifies multiple consecutive database initializations succeed without schema conflict."""
        db = BinaryDatabaseEngine()
        # Verify schema table existences
        cfg1 = db.get_cache_config()
        self.assertIsNotNone(cfg1)

        # Re-run migration / column additions idempotently
        db._init_db()
        db._init_db()

        cfg2 = db.get_cache_config()
        self.assertEqual(cfg1["enabled"], cfg2["enabled"])

    async def test_client_disconnect_cleanup(self):
        """Verifies in-flight slot cleanup when request task is cancelled (client disconnect)."""
        email = "client_disc@example.com"
        AccountFailoverPool.acquire(email)
        self.assertEqual(AccountFailoverPool.get_in_flight_count(email), 1)

        async def dummy_streaming_task():
            try:
                while True:
                    await asyncio.sleep(0.01)
            finally:
                AccountFailoverPool.release(email)

        task = asyncio.create_task(dummy_streaming_task())
        await asyncio.sleep(0.02)
        
        # Simulate client disconnect by cancelling task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # In-flight count must drop back to 0
        self.assertEqual(AccountFailoverPool.get_in_flight_count(email), 0)

    async def test_concurrency_light_load(self):
        """Light concurrency test: 10 concurrent async operations acquire/release cleanly."""
        email = "load_test@example.com"
        
        async def worker(worker_id: int):
            AccountFailoverPool.acquire(email)
            await asyncio.sleep(0.01)
            AccountFailoverPool.release(email)
            return worker_id

        tasks = [worker(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        self.assertEqual(len(results), 10)
        self.assertEqual(AccountFailoverPool.get_in_flight_count(email), 0)

if __name__ == "__main__":
    unittest.main()
