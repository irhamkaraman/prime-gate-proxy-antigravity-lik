import unittest
from prime_gate.db import db
from prime_gate.resilience import AccountFailoverPool


class TestAutoUpdate(unittest.TestCase):
    def test_auto_update_config_default_enabled(self):
        cfg = db.get_auto_update_config()
        self.assertIsInstance(cfg, dict)
        self.assertTrue(cfg.get("enabled"))
        self.assertEqual(cfg.get("check_interval_seconds"), 600)
        self.assertEqual(cfg.get("idle_threshold_seconds"), 30)
        self.assertTrue(cfg.get("auto_rebuild_ui"))
        self.assertFalse(cfg.get("auto_apply", False))

    def test_auto_update_config_mutation(self):
        # Mutate config
        db.set_auto_update_config({"idle_threshold_seconds": 45})
        cfg = db.get_auto_update_config()
        self.assertEqual(cfg.get("idle_threshold_seconds"), 45)
        # Restore default
        db.set_auto_update_config({"idle_threshold_seconds": 30})

    def test_auto_update_ledger_recording(self):
        row_id = db.record_auto_update_event(
            status="success",
            from_commit="abc1111",
            to_commit="xyz2222",
            from_version="1.2.2",
            to_version="1.2.3",
            ui_rebuilt=True,
            log="Unit test auto-update entry"
        )
        self.assertGreater(row_id, 0)

        logs = db.get_auto_update_logs(limit=5)
        self.assertIsInstance(logs, list)
        self.assertGreaterEqual(len(logs), 1)
        latest = logs[0]
        self.assertEqual(latest["status"], "success")
        self.assertEqual(latest["to_version"], "1.2.3")
        self.assertTrue(latest["ui_rebuilt"])

    def test_account_failover_in_flight(self):
        total = AccountFailoverPool.get_total_in_flight()
        self.assertGreaterEqual(total, 0)


if __name__ == "__main__":
    unittest.main()
