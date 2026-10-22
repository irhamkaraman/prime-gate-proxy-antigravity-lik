import os
import unittest
from prime_gate.crypto.cipher import AESGCMCipher, DecryptionError
from prime_gate.crypto.key_manager import KeyManager
from prime_gate.db.binary_codec import BinaryCodec, DatabaseCorruptedError, REC_SYSTEM


class TestEncryptionAESGCM(unittest.TestCase):
    def setUp(self):
        self.master_key = KeyManager.get_master_key()
        self.test_payload = {
            "email": "developer@example.com",
            "refreshToken": "1//04test_refresh_token_secret",
            "token": "ya29.a0AWY7Ckk_test_access_token",
            "count": 42
        }

    def test_aes_gcm_encrypt_decrypt_roundtrip(self):
        blob = AESGCMCipher.encrypt(REC_SYSTEM, self.test_payload, record_key="test:auth", key=self.master_key)
        self.assertIsInstance(blob, bytes)
        self.assertGreater(len(blob), 36)

        rec_type, decrypted, ts = AESGCMCipher.decrypt(blob, record_key="test:auth", key=self.master_key)
        self.assertEqual(rec_type, REC_SYSTEM)
        self.assertEqual(decrypted, self.test_payload)
        self.assertGreater(ts, 0)

    def test_random_nonce_per_encryption(self):
        blob1 = AESGCMCipher.encrypt(REC_SYSTEM, self.test_payload, record_key="test:auth", key=self.master_key)
        blob2 = AESGCMCipher.encrypt(REC_SYSTEM, self.test_payload, record_key="test:auth", key=self.master_key)
        # Even with identical payload, key, and record_key, the ciphertext must differ due to random 12-byte nonce
        self.assertNotEqual(blob1, blob2)

    def test_tampered_ciphertext_fails_auth_tag(self):
        blob = bytearray(AESGCMCipher.encrypt(REC_SYSTEM, self.test_payload, record_key="test:auth", key=self.master_key))
        # Tamper with the last byte of the ciphertext (authentication tag region)
        blob[-1] ^= 0xFF
        with self.assertRaises(DecryptionError):
            AESGCMCipher.decrypt(bytes(blob), record_key="test:auth", key=self.master_key)

    def test_aad_binding_prevents_swap_attack(self):
        # Ciphertext encrypted for "record_A" must fail when unpacked as "record_B"
        blob = AESGCMCipher.encrypt(REC_SYSTEM, self.test_payload, record_key="record_A", key=self.master_key)
        with self.assertRaises(DecryptionError):
            AESGCMCipher.decrypt(blob, record_key="record_B", key=self.master_key)

    def test_binary_codec_v2_pack_unpack(self):
        blob = BinaryCodec.pack(REC_SYSTEM, self.test_payload, key_name="sys:config")
        magic, version, rec_type, plen, crc, ts = BinaryCodec.extract_header(blob)
        self.assertEqual(magic, b"PGDB")
        self.assertEqual(version, 2)
        self.assertEqual(rec_type, REC_SYSTEM)

        rec_type_out, payload_out, _ = BinaryCodec.unpack(blob, key_name="sys:config")
        self.assertEqual(rec_type_out, REC_SYSTEM)
        self.assertEqual(payload_out, self.test_payload)


if __name__ == "__main__":
    unittest.main()
