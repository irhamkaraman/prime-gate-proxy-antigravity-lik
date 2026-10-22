import unittest
from prime_gate.db import db


class TestAutoUpdateSecurity(unittest.TestCase):
    def test_auto_update_defaults_to_notify_only(self):
        cfg = db.get_auto_update_config()
        # auto_apply must be False by default so releases are not automatically installed without consent
        self.assertFalse(cfg.get("auto_apply", False))
        # enabled is True for background release checking/notifications
        self.assertTrue(cfg.get("enabled", True))

    def test_auto_apply_opt_in(self):
        db.set_auto_update_config({"auto_apply": True})
        cfg = db.get_auto_update_config()
        self.assertTrue(cfg.get("auto_apply"))
        # Reset back to False
        db.set_auto_update_config({"auto_apply": False})
        self.assertFalse(db.get_auto_update_config().get("auto_apply"))


if __name__ == "__main__":
    unittest.main()
