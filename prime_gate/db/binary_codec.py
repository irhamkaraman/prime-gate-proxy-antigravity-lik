import os
import time
import zlib
import json
import struct
from typing import Dict, Any, Tuple, Optional

from ..crypto.cipher import (
    AESGCMCipher,
    DecryptionError,
    FORMAT_VERSION_V2,
    HEADER_FORMAT_V2,
    HEADER_SIZE_V2
)
from ..crypto.key_manager import KeyManager

MAGIC_HEADER = b"PGDB"
FORMAT_VERSION_V1 = 1
FORMAT_VERSION = FORMAT_VERSION_V2

# Record Type Identifiers
REC_ACCOUNT = 1
REC_MODEL = 2
REC_QUOTA = 3
REC_SYSTEM = 4
REC_LOG = 5

# Legacy V1 Header format (24 bytes)
HEADER_FORMAT_V1 = ">4sHHIIQ"
HEADER_SIZE_V1 = struct.calcsize(HEADER_FORMAT_V1)

# Legacy XOR mask key for V1 backwards compatibility
_LEGACY_SALT = (
    b"\x9a\x3f\x7b\x1c\x8e\x2d\x4a\x5f\xb0\x11\x4e\x8d\x7c\x2b\x6a\x9f"
    b"\x33\x5a\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff\x00\x12\x34\x56\x78"
    b"\xfe\xdc\xba\x98\x76\x54\x32\x10\x0f\x1e\x2d\x3c\x4b\x5a\x69\x78"
    b"\xa1\xb2\xc3\xd4\xe5\xf6\x07\x18\x29\x3a\x4b\x5c\x6d\x7e\x8f\x90"
)


class DatabaseCorruptedError(Exception):
    """Raised when binary record integrity validation fails (CRC32, AES-GCM Tag, magic header, or truncated payload)."""
    def __init__(self, message: str, key: str = "", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.key = key
        self.details = details or {}


def _legacy_xor_transform(data: bytes, key: bytes = _LEGACY_SALT) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


class BinaryCodec:
    """
    High-performance binary serialization codec for Prime Gate database.
    - Default V2: AES-256-GCM authenticated encryption + Zlib + CRC32 integrity check.
    - Legacy V1 fallback: Unpacks older XOR-obfuscated records for seamless idempotent migration.
    """

    @staticmethod
    def pack(
        record_type: int,
        payload: Dict[str, Any],
        key_name: str = "",
        key: Optional[bytes] = None
    ) -> bytes:
        """Serializes a dictionary payload into an AES-256-GCM encrypted binary blob."""
        return AESGCMCipher.encrypt(record_type, payload, record_key=key_name, key=key)

    @staticmethod
    def extract_header(blob: bytes) -> Tuple[bytes, int, int, int, int, int]:
        """Extracts (magic, version, record_type, payload_len, stored_crc, timestamp_ms) from binary blob."""
        if not blob or len(blob) < 8:
            raise DatabaseCorruptedError("Binary blob is truncated: Expected at least 8 bytes")
        magic, version = struct.unpack(">4sH", blob[:6])
        if version == FORMAT_VERSION_V2:
            if len(blob) < HEADER_SIZE_V2:
                raise DatabaseCorruptedError("V2 Binary blob truncated")
            magic, version, record_type, nonce, payload_len, stored_crc, timestamp_ms = struct.unpack(
                HEADER_FORMAT_V2, blob[:HEADER_SIZE_V2]
            )
            return magic, version, record_type, payload_len, stored_crc, timestamp_ms
        else:
            if len(blob) < HEADER_SIZE_V1:
                raise DatabaseCorruptedError("V1 Binary blob truncated")
            magic, version, record_type, payload_len, stored_crc, timestamp_ms = struct.unpack(
                HEADER_FORMAT_V1, blob[:HEADER_SIZE_V1]
            )
            return magic, version, record_type, payload_len, stored_crc, timestamp_ms

    @staticmethod
    def unpack(
        blob: bytes,
        key_name: str = "",
        key: Optional[bytes] = None
    ) -> Tuple[int, Dict[str, Any], int]:
        """
        Unpacks and verifies an integrity-sealed binary blob.
        Supports automatic dual-version parsing (V2 AES-256-GCM or V1 legacy XOR).
        Raises DatabaseCorruptedError if corrupted or tampered.
        Returns: (record_type, payload_dict, timestamp_ms)
        """
        if not blob or len(blob) < 8:
            raise DatabaseCorruptedError(
                f"Binary record is truncated: Expected at least 8 bytes, got {len(blob) if blob else 0}",
                key=key_name
            )

        magic, version, record_type = struct.unpack(">4sHH", blob[:8])
        if magic != MAGIC_HEADER:
            raise DatabaseCorruptedError(
                f"Invalid binary magic signature: Expected {MAGIC_HEADER!r}, found {magic!r}",
                key=key_name,
                details={"magic_found": str(magic)}
            )

        if version == FORMAT_VERSION_V2:
            try:
                return AESGCMCipher.decrypt(blob, record_key=key_name, key=key)
            except DecryptionError as de:
                raise DatabaseCorruptedError(str(de), key=key_name, details=de.details)

        elif version == FORMAT_VERSION_V1:
            # Unpack legacy V1 record
            if len(blob) < HEADER_SIZE_V1:
                raise DatabaseCorruptedError(
                    f"Legacy V1 record truncated: Expected at least {HEADER_SIZE_V1} bytes",
                    key=key_name
                )
            magic, version, rec_type, payload_len, stored_crc, timestamp_ms = struct.unpack(
                HEADER_FORMAT_V1, blob[:HEADER_SIZE_V1]
            )
            masked_payload = blob[HEADER_SIZE_V1:]
            if len(masked_payload) != payload_len:
                raise DatabaseCorruptedError(
                    f"Payload size mismatch: Header declares {payload_len} bytes, actual is {len(masked_payload)} bytes",
                    key=key_name
                )
            computed_crc = zlib.crc32(masked_payload) & 0xFFFFFFFF
            if computed_crc != stored_crc:
                raise DatabaseCorruptedError(
                    f"CRC32 Checksum Mismatch! Data corruption detected (Stored: {hex(stored_crc)}, Computed: {hex(computed_crc)})",
                    key=key_name,
                    details={"stored_crc": hex(stored_crc), "computed_crc": hex(computed_crc)}
                )
            try:
                compressed = _legacy_xor_transform(masked_payload)
                json_bytes = zlib.decompress(compressed)
                payload_dict = json.loads(json_bytes.decode('utf-8'))
                return rec_type, payload_dict, timestamp_ms
            except Exception as e:
                raise DatabaseCorruptedError(
                    f"Failed to decompress and decode legacy binary payload: {e}",
                    key=key_name,
                    details={"error": str(e)}
                )
        else:
            raise DatabaseCorruptedError(
                f"Unknown database format version: {version}",
                key=key_name
            )
