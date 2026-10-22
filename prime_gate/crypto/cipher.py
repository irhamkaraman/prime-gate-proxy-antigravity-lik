import os
import time
import zlib
import json
import struct
from typing import Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from .key_manager import KeyManager

MAGIC_HEADER = b"PGDB"
FORMAT_VERSION_V2 = 2

# V2 Header Format:
# 4s : Magic Header (PGDB)
# H  : Format Version (2)
# H  : Record Type (1=Account, 2=Model, etc.)
# 12s: Random Nonce (12 bytes for AES-GCM)
# I  : Ciphertext Length
# I  : CRC32 of Ciphertext
# Q  : Timestamp in ms
HEADER_FORMAT_V2 = ">4sHH12sIIQ"
HEADER_SIZE_V2 = struct.calcsize(HEADER_FORMAT_V2)  # 36 bytes


class DecryptionError(Exception):
    """Raised when AES-GCM decryption or authentication tag verification fails."""
    def __init__(self, message: str, key: str = "", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.key = key
        self.details = details or {}


class AESGCMCipher:
    """
    AES-256-GCM Authenticated Encryption Codec for Prime Gate Database.
    Ensures confidentiality, authenticity, and storage integrity for credentials at rest.
    - 256-bit key from OS Keyring / Scrypt KDF
    - 96-bit (12-byte) cryptographically secure unique nonce per record
    - 128-bit (16-byte) GCM authentication tag
    - Additional Authenticated Data (AAD) bound to the record key to prevent swap attacks
    - 32-bit CRC32 checksum for storage integrity verification
    """

    @staticmethod
    def encrypt(
        record_type: int,
        payload: Dict[str, Any],
        record_key: str = "",
        key: Optional[bytes] = None
    ) -> bytes:
        master_key = key or KeyManager.get_master_key()
        aesgcm = AESGCM(master_key)

        json_bytes = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        compressed = zlib.compress(json_bytes, level=6)

        nonce = os.urandom(12)
        aad = f"PGDB_V2:{record_key}".encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, compressed, aad)

        payload_len = len(ciphertext)
        payload_crc = zlib.crc32(ciphertext) & 0xFFFFFFFF
        timestamp_ms = int(time.time() * 1000)

        header = struct.pack(
            HEADER_FORMAT_V2,
            MAGIC_HEADER,
            FORMAT_VERSION_V2,
            record_type,
            nonce,
            payload_len,
            payload_crc,
            timestamp_ms
        )

        return header + ciphertext

    @staticmethod
    def decrypt(
        blob: bytes,
        record_key: str = "",
        key: Optional[bytes] = None
    ) -> Tuple[int, Dict[str, Any], int]:
        if not blob or len(blob) < HEADER_SIZE_V2:
            raise DecryptionError(
                f"Binary record is truncated: Expected at least {HEADER_SIZE_V2} bytes",
                key=record_key,
                details={"actual_size": len(blob) if blob else 0}
            )

        magic, version, record_type, nonce, payload_len, stored_crc, timestamp_ms = struct.unpack(
            HEADER_FORMAT_V2, blob[:HEADER_SIZE_V2]
        )

        if magic != MAGIC_HEADER:
            raise DecryptionError(
                f"Invalid magic signature: Expected {MAGIC_HEADER!r}, found {magic!r}",
                key=record_key
            )

        if version != FORMAT_VERSION_V2:
            raise DecryptionError(
                f"Unsupported format version: Expected {FORMAT_VERSION_V2}, found {version}",
                key=record_key
            )

        ciphertext = blob[HEADER_SIZE_V2:]
        if len(ciphertext) != payload_len:
            raise DecryptionError(
                f"Payload size mismatch: Header declares {payload_len} bytes, got {len(ciphertext)} bytes",
                key=record_key
            )

        # 1. CRC32 storage integrity verification
        computed_crc = zlib.crc32(ciphertext) & 0xFFFFFFFF
        if computed_crc != stored_crc:
            raise DecryptionError(
                f"CRC32 Checksum Mismatch! Data corruption detected (Stored: {hex(stored_crc)}, Computed: {hex(computed_crc)})",
                key=record_key,
                details={"stored_crc": hex(stored_crc), "computed_crc": hex(computed_crc)}
            )

        # 2. AES-256-GCM Authenticated Decryption
        master_key = key or KeyManager.get_master_key()
        aesgcm = AESGCM(master_key)
        aad = f"PGDB_V2:{record_key}".encode("utf-8")

        try:
            compressed = aesgcm.decrypt(nonce, ciphertext, aad)
        except InvalidTag:
            raise DecryptionError(
                "AES-GCM Authentication Tag mismatch! Record ciphertext has been tampered with or master key is invalid.",
                key=record_key
            )
        except Exception as e:
            raise DecryptionError(f"AES-GCM Decryption failed: {e}", key=record_key)

        # 3. Zlib decompress & JSON decode
        try:
            json_bytes = zlib.decompress(compressed)
            payload_dict = json.loads(json_bytes.decode('utf-8'))
            return record_type, payload_dict, timestamp_ms
        except Exception as e:
            raise DecryptionError(f"Decompression/JSON decode error: {e}", key=record_key)
