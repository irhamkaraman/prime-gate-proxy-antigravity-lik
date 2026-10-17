import os
import time
import zlib
import json
import struct
from typing import Dict, Any, Tuple, Optional

MAGIC_HEADER = b"PGDB"
FORMAT_VERSION = 1

# Record Type Identifiers
REC_ACCOUNT = 1
REC_MODEL = 2
REC_QUOTA = 3
REC_SYSTEM = 4
REC_LOG = 5

HEADER_FORMAT = ">4sHHIIQ"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 24 bytes

# Deterministic XOR Mask Key (64 bytes high-entropy binary seed)
_DEFAULT_SALT = (
    b"\x9a\x3f\x7b\x1c\x8e\x2d\x4a\x5f\xb0\x11\x4e\x8d\x7c\x2b\x6a\x9f"
    b"\x33\x5a\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff\x00\x12\x34\x56\x78"
    b"\xfe\xdc\xba\x98\x76\x54\x32\x10\x0f\x1e\x2d\x3c\x4b\x5a\x69\x78"
    b"\xa1\xb2\xc3\xd4\xe5\xf6\x07\x18\x29\x3a\x4b\x5c\x6d\x7e\x8f\x90"
)

class DatabaseCorruptedError(Exception):
    """Raised when binary record integrity validation fails (CRC32, magic header, or truncated payload)."""
    def __init__(self, message: str, key: str = "", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.key = key
        self.details = details or {}


def _xor_transform(data: bytes, key: bytes = _DEFAULT_SALT) -> bytes:
    """Fast XOR obfuscation to eliminate readable plaintext strings and JSON structures."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


class BinaryCodec:
    """
    High-performance binary serialization codec for Prime Gate database.
    Packs arbitrary dictionary payloads into compact, non-readable binary blobs with:
    - 24-byte binary magic header (PGDB)
    - High-ratio Zlib compression (level 6)
    - XOR-mask obfuscation (prevents plain-text token / credential leakage)
    - Strict 32-bit CRC32 checksum integrity verification
    """

    @staticmethod
    def pack(record_type: int, payload: Dict[str, Any], key: bytes = _DEFAULT_SALT) -> bytes:
        """Serializes a dictionary payload into an integrity-sealed binary blob."""
        json_bytes = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        compressed = zlib.compress(json_bytes, level=6)
        masked_payload = _xor_transform(compressed, key)

        payload_len = len(masked_payload)
        payload_crc = zlib.crc32(masked_payload) & 0xFFFFFFFF
        timestamp_ms = int(time.time() * 1000)

        header = struct.pack(
            HEADER_FORMAT,
            MAGIC_HEADER,
            FORMAT_VERSION,
            record_type,
            payload_len,
            payload_crc,
            timestamp_ms
        )

        return header + masked_payload

    @staticmethod
    def extract_header(blob: bytes) -> Tuple[bytes, int, int, int, int, int]:
        """Extracts (magic, version, record_type, payload_len, stored_crc, timestamp_ms)."""
        if not blob or len(blob) < HEADER_SIZE:
            raise DatabaseCorruptedError(f"Binary blob is truncated: Expected at least {HEADER_SIZE} bytes")
        return struct.unpack(HEADER_FORMAT, blob[:HEADER_SIZE])

    @staticmethod
    def unpack(blob: bytes, key_name: str = "", key: bytes = _DEFAULT_SALT) -> Tuple[int, Dict[str, Any], int]:
        """
        Unpacks and verifies an integrity-sealed binary blob.
        Raises DatabaseCorruptedError immediately if corrupted or tampered.
        Returns: (record_type, payload_dict, timestamp_ms)
        """
        if not blob or len(blob) < HEADER_SIZE:
            raise DatabaseCorruptedError(
                f"Binary record is truncated: Expected at least {HEADER_SIZE} bytes, got {len(blob)} bytes",
                key=key_name,
                details={"actual_size": len(blob), "expected_min": HEADER_SIZE}
            )

        try:
            magic, version, record_type, payload_len, stored_crc, timestamp_ms = struct.unpack(
                HEADER_FORMAT, blob[:HEADER_SIZE]
            )
        except Exception as e:
            raise DatabaseCorruptedError(
                f"Binary record header unpack error: {e}",
                key=key_name,
                details={"error": str(e)}
            )

        if magic != MAGIC_HEADER:
            raise DatabaseCorruptedError(
                f"Invalid binary magic signature: Expected {MAGIC_HEADER!r}, found {magic!r}",
                key=key_name,
                details={"magic_found": str(magic)}
            )

        masked_payload = blob[HEADER_SIZE:]
        if len(masked_payload) != payload_len:
            raise DatabaseCorruptedError(
                f"Payload size mismatch: Header declares {payload_len} bytes, actual is {len(masked_payload)} bytes",
                key=key_name,
                details={"declared_len": payload_len, "actual_len": len(masked_payload)}
            )

        computed_crc = zlib.crc32(masked_payload) & 0xFFFFFFFF
        if computed_crc != stored_crc:
            raise DatabaseCorruptedError(
                f"CRC32 Checksum Mismatch! Data corruption detected (Stored: {hex(stored_crc)}, Computed: {hex(computed_crc)})",
                key=key_name,
                details={"stored_crc": hex(stored_crc), "computed_crc": hex(computed_crc)}
            )

        try:
            compressed = _xor_transform(masked_payload, key)
            json_bytes = zlib.decompress(compressed)
            payload_dict = json.loads(json_bytes.decode('utf-8'))
            return record_type, payload_dict, timestamp_ms
        except Exception as e:
            raise DatabaseCorruptedError(
                f"Failed to decompress and decode binary payload: {e}",
                key=key_name,
                details={"error": str(e)}
            )
