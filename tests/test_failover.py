import unittest
import time
from prime_gate.resilience import AccountFailoverPool

class TestAccountFailoverPool(unittest.TestCase):
    def setUp(self):
        AccountFailoverPool._cooldowns.clear()

    def test_failover_selection(self):
        accounts = [
            {"email": "acc1@gmail.com", "name": "Account 1"},
            {"email": "acc2@gmail.com", "name": "Account 2"},
            {"email": "acc3@gmail.com", "name": "Account 3"}
        ]
        # Current is acc1, mark acc2 in cooldown
        AccountFailoverPool.mark_rate_limited("acc2@gmail.com", cooldown_seconds=60)
        
        # Next failover account should be acc3
        failover = AccountFailoverPool.get_failover_account("acc1@gmail.com", accounts)
        self.assertIsNotNone(failover)
        self.assertEqual(failover["email"], "acc3@gmail.com")

    def test_cooldown_expiry(self):
        AccountFailoverPool.mark_rate_limited("temp@gmail.com", cooldown_seconds=0.01)
        time.sleep(0.02)
        self.assertTrue(AccountFailoverPool.is_available({"email": "temp@gmail.com"}))

    def test_get_ordered_accounts(self):
        accounts = [
            {"email": "acc1@gmail.com"},
            {"email": "acc2@gmail.com"},
            {"email": "acc3@gmail.com"}
        ]
        # Mark acc1 as rate limited
        AccountFailoverPool.mark_rate_limited("acc1@gmail.com", cooldown_seconds=60)
        ordered = AccountFailoverPool.get_ordered_accounts(accounts, preferred_account=accounts[0])
        self.assertEqual(len(ordered), 3)
        # acc2 and acc3 are healthy so they should be first, acc1 (cooling) should be last
        self.assertIn(ordered[0]["email"], ["acc2@gmail.com", "acc3@gmail.com"])
        self.assertEqual(ordered[-1]["email"], "acc1@gmail.com")

if __name__ == "__main__":
    unittest.main()

