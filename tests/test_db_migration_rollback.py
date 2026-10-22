import os
import time
import struct
import zlib
import json
import unittest
from pathlib import Path
from prime_gate.db import db, REC_ACCOUNT, REC_SYSTEM
from prime_gate.db.binary_codec import BinaryCodec, HEADER_FORMAT_V1, _legacy_xor_transform


class TestDBMigrationRollback(unittest.TestCase):
    def test_legacy_v1_decoding_and_auto_migration(self):
        # 1. Manually craft a legacy V1 XOR record
        payload = {"account": "legacy@user.com", "refreshToken": "1//legacy_token_123"}
        json_bytes = json.dumps(payload).encode('utf-8')
        compressed = zlib.compress(json_bytes, level=6)
        masked = _legacy_xor_transform(compressed)
        v1_header = struct.pack(
            HEADER_FORMAT_V1,
            b"PGDB",
            1,  # Version 1
            REC_ACCOUNT,
            len(masked),
            zlib.crc32(masked) & 0xFFFFFFFF,
            int(time.time() * 1000)
        )
        v1_blob = v1_header + masked

        # 2. Test that BinaryCodec correctly unpacks legacy V1
        rec_type, unpacked, _ = BinaryCodec.unpack(v1_blob, key_name="test:legacy_acc")
        self.assertEqual(rec_type, REC_ACCOUNT)
        self.assertEqual(unpacked, payload)

        # 3. Store v1 blob in DB and trigger migration
        conn = db._get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO pg_records (key, record_type, data, crc32, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("test:legacy_acc", REC_ACCOUNT, v1_blob, 0, time.time())
        )
        migrated_count = db.migrate_v1_to_v2()
        self.assertGreaterEqual(migrated_count, 1)

        # 4. Verify record in DB is now Version 2 (AES-256-GCM)
        row = conn.execute("SELECT data FROM pg_records WHERE key = ?", ("test:legacy_acc",)).fetchone()
        self.assertIsNotNone(row)
        blob = row["data"]
        magic, version = struct.unpack(">4sH", blob[:6])
        self.assertEqual(magic, b"PGDB")
        self.assertEqual(version, 2)

        # Clean up
        db.delete("test:legacy_acc")

    def test_backup_and_rollback(self):
        # Write test key
        db.set("test:backup_key", {"state": "initial"})
        backup_file = db.create_backup("unit_test")
        self.assertTrue(backup_file.exists())

        # Mutate key
        db.set("test:backup_key", {"state": "modified"})
        self.assertEqual(db.get("test:backup_key")["state"], "modified")

        # Rollback from backup
        success = db.rollback_from_backup(backup_file)
        self.assertTrue(success)
        self.assertEqual(db.get("test:backup_key")["state"], "initial")

        # Clean up
        db.delete("test:backup_key")
        if backup_file.exists():
            backup_file.unlink()

    def test_key_rotation(self):
        db.set("test:rotation_key", {"secret": "super_secret_val"})
        success = db.rotate_database_key()
        self.assertTrue(success)
        val = db.get("test:rotation_key")
        self.assertEqual(val["secret"], "super_secret_val")
        db.delete("test:rotation_key")


if __name__ == "__main__":
    unittest.main()
