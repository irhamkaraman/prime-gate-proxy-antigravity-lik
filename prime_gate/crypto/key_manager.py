import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("prime_gate.crypto.key_manager")

SERVICE_NAME = "prime_gate"
KEY_USERNAME = "master_key"

try:
    import keyring
    import keyring.errors
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False


class KeyManager:
    """
    Manages the 256-bit database master encryption key.
    Prioritizes OS Keyring (DPAPI on Windows, Keychain on macOS, SecretService on Linux).
    Falls back to user passphrase with Scrypt KDF or a protected local keyfile.
    """

    @classmethod
    def get_keyfile_path(cls) -> Path:
        base_dir = Path(__file__).resolve().parent.parent.parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / ".pg_master.key"

    @classmethod
    def derive_from_passphrase(cls, passphrase: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        if salt is None:
            salt = b"prime_gate_scrypt_salt_v2"
        kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
        key = kdf.derive(passphrase.encode("utf-8"))
        return key, salt

    @classmethod
    def get_master_key(cls) -> bytes:
        """
        Retrieves or generates the 32-byte (256-bit) master encryption key.
        Priority:
        1. Environment variable PRIME_GATE_MASTER_KEY (hex or raw 32 bytes)
        2. Environment variable PRIME_GATE_PASSPHRASE (Scrypt KDF)
        3. OS Keyring (DPAPI / Keychain / SecretService)
        4. Protected local keyfile fallback (with loud security warning)
        """
        # 1. Environment variable override
        env_key = os.getenv("PRIME_GATE_MASTER_KEY")
        if env_key:
            try:
                raw = bytes.fromhex(env_key.strip())
                if len(raw) == 32:
                    return raw
            except Exception:
                pass
            if len(env_key.encode("utf-8")) == 32:
                return env_key.encode("utf-8")

        # 2. Passphrase env override
        passphrase = os.getenv("PRIME_GATE_PASSPHRASE")
        if passphrase:
            key, _ = cls.derive_from_passphrase(passphrase)
            return key

        # 3. OS Keyring
        if KEYRING_AVAILABLE and keyring is not None:
            try:
                stored = keyring.get_password(SERVICE_NAME, KEY_USERNAME)
                if stored:
                    key = bytes.fromhex(stored)
                    if len(key) == 32:
                        return key
                # Generate new key and store in keyring
                new_key = os.urandom(32)
                keyring.set_password(SERVICE_NAME, KEY_USERNAME, new_key.hex())
                logger.info("Generated new 256-bit master key and stored in OS Keyring.")
                return new_key
            except Exception as e:
                logger.warning(f"OS Keyring retrieval/storage failed: {e}. Falling back to local keyfile.")

        # 4. Fallback: local keyfile
        keyfile = cls.get_keyfile_path()
        if keyfile.exists():
            try:
                hex_data = keyfile.read_text(encoding="utf-8").strip()
                key = bytes.fromhex(hex_data)
                if len(key) == 32:
                    return key
            except Exception as e:
                logger.error(f"Failed reading local keyfile: {e}")

        # Generate and save in local keyfile
        new_key = os.urandom(32)
        try:
            keyfile.write_text(new_key.hex(), encoding="utf-8")
            # Restrict permissions on POSIX
            if sys.platform != "win32":
                try:
                    os.chmod(keyfile, 0o600)
                except Exception:
                    pass
            logger.warning(
                "====================================================================\n"
                "SECURITY WARNING: OS Keyring unavailable. Using local keyfile fallback\n"
                f"at {keyfile}. Ensure filesystem permissions are restricted!\n"
                "===================================================================="
            )
            return new_key
        except Exception as e:
            logger.critical(f"Failed to persist master key to keyfile: {e}")
            raise RuntimeError(f"Could not initialize database master key: {e}")

    @classmethod
    def rotate_master_key(cls, new_key: Optional[bytes] = None) -> bytes:
        """Generates or sets a new master key and saves it into the active storage."""
        if new_key is None:
            new_key = os.urandom(32)
        if len(new_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes (256 bits)")

        saved = False
        if KEYRING_AVAILABLE and keyring is not None:
            try:
                keyring.set_password(SERVICE_NAME, KEY_USERNAME, new_key.hex())
                saved = True
            except Exception as e:
                logger.warning(f"Keyring update during rotation failed: {e}")

        # Update local keyfile as well if it exists or if keyring failed
        keyfile = cls.get_keyfile_path()
        try:
            keyfile.write_text(new_key.hex(), encoding="utf-8")
            saved = True
        except Exception as e:
            if not saved:
                raise RuntimeError(f"Failed to persist rotated master key: {e}")

        logger.info("Master encryption key successfully rotated.")
        return new_key
