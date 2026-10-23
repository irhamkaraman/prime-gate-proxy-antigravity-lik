import os
import time
import hmac
import hashlib
import secrets
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

COOKIE_SESSION_NAME = "pg_session"
COOKIE_CSRF_NAME = "pg_csrf"
HEADER_CSRF_NAME = "x-csrf-token"

# In-memory storage for active sessions & rate limiting
# session_id -> { "created_at": float, "expires_at": float, "csrf_token": str, "key_name": str }
_ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_TTL_SECONDS = 315360000  # 10 years (persistent permanent session)

# IP -> list of failed attempt timestamps
_FAILED_LOGINS: Dict[str, List[float]] = defaultdict(list)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes


class AuthManager:
    """
    Unified Authentication and Session Manager for Prime Gate:
    - API Key generation (SHA-256 + salt) and constant-time verification.
    - Dashboard HttpOnly session management.
    - Double-submit CSRF token issuance and verification.
    - Brute-force rate limiting for failed login attempts.
    """

    @staticmethod
    def hash_key(raw_key: str, salt: bytes) -> str:
        """Computes SHA-256 digest of salt + raw_key."""
        return hashlib.sha256(salt + raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_api_key(name: str = "default") -> Tuple[str, Dict[str, Any]]:
        """
        Generates a new secure random API key.
        Returns (raw_key, record_dict).
        Raw key should be displayed to the user ONCE.
        """
        random_part = secrets.token_hex(16)  # 32 hex chars
        raw_key = f"pg-live-{random_part}"
        salt = os.urandom(16)
        salt_hex = salt.hex()
        key_hash = AuthManager.hash_key(raw_key, salt)
        prefix = f"pg-live-{random_part[:4]}..."

        record = {
            "name": name,
            "prefix": prefix,
            "key_hash": key_hash,
            "salt": salt_hex,
            "created_at": time.time(),
            "last_used_at": None,
            "revoked_at": None
        }
        return raw_key, record

    @staticmethod
    def verify_api_key(raw_key: str, active_keys: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Constant-time verification of an API key against a list of active key records.
        Returns the matched key record or None.
        """
        if not raw_key or not active_keys:
            return None

        matched_record = None
        for record in active_keys:
            if record.get("revoked_at") is not None:
                continue
            salt_hex = record.get("salt", "")
            expected_hash = record.get("key_hash", "")
            try:
                salt = bytes.fromhex(salt_hex)
                computed_hash = AuthManager.hash_key(raw_key, salt)
                if hmac.compare_digest(computed_hash, expected_hash):
                    matched_record = record
            except Exception:
                pass

        return matched_record

    # -------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------
    @staticmethod
    def is_rate_limited(client_ip: str) -> Tuple[bool, int]:
        """Checks if a client IP is currently rate-limited due to failed attempts."""
        now = time.time()
        attempts = [t for t in _FAILED_LOGINS.get(client_ip, []) if now - t < LOCKOUT_WINDOW_SECONDS]
        _FAILED_LOGINS[client_ip] = attempts

        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            remaining_seconds = int(LOCKOUT_WINDOW_SECONDS - (now - attempts[0]))
            return True, max(1, remaining_seconds)
        return False, 0

    @staticmethod
    def record_login_attempt(client_ip: str, success: bool):
        """Records a login attempt; clears history on success."""
        if success:
            _FAILED_LOGINS.pop(client_ip, None)
        else:
            _FAILED_LOGINS[client_ip].append(time.time())

    # -------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------
    @staticmethod
    def create_session(key_name: str = "") -> Tuple[str, str]:
        """
        Creates a persistent dashboard session.
        Returns (session_id, csrf_token).
        Persists session in binary DB to survive server & daemon restarts.
        """
        now = time.time()
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)

        session_data = {
            "created_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
            "csrf_token": csrf_token,
            "key_name": key_name
        }
        _ACTIVE_SESSIONS[session_id] = session_data

        try:
            from ..db import db
            db.set(f"session:{session_id}", session_data)
        except Exception:
            pass

        return session_id, csrf_token

    @staticmethod
    def validate_session(session_id: Optional[str]) -> bool:
        """Validates that a session exists and has not expired (memory + persistent DB)."""
        if not session_id:
            return False

        session = _ACTIVE_SESSIONS.get(session_id)
        if not session:
            try:
                from ..db import db
                data = db.get(f"session:{session_id}")
                if data and isinstance(data, dict):
                    _ACTIVE_SESSIONS[session_id] = data
                    session = data
            except Exception:
                pass

        if not session:
            return False

        if time.time() > session.get("expires_at", 0):
            _ACTIVE_SESSIONS.pop(session_id, None)
            try:
                from ..db import db
                db.delete(f"session:{session_id}")
            except Exception:
                pass
            return False
        return True

    @staticmethod
    def get_csrf_token_for_session(session_id: Optional[str]) -> Optional[str]:
        """Returns the CSRF token associated with an active session."""
        if not session_id:
            return None

        session = _ACTIVE_SESSIONS.get(session_id)
        if not session:
            try:
                from ..db import db
                data = db.get(f"session:{session_id}")
                if data and isinstance(data, dict):
                    _ACTIVE_SESSIONS[session_id] = data
                    session = data
            except Exception:
                pass

        if session and time.time() <= session.get("expires_at", 0):
            return session.get("csrf_token")
        return None

    @staticmethod
    def validate_csrf(session_id: Optional[str], header_token: Optional[str]) -> bool:
        """Validates that the provided CSRF token matches the session CSRF token."""
        if not session_id or not header_token:
            return False
        expected_csrf = AuthManager.get_csrf_token_for_session(session_id)
        if not expected_csrf:
            return False
        return hmac.compare_digest(header_token, expected_csrf)

    @staticmethod
    def destroy_session(session_id: Optional[str]):
        """Invalidates a session on logout from memory and persistent database."""
        if session_id:
            _ACTIVE_SESSIONS.pop(session_id, None)
            try:
                from ..db import db
                db.delete(f"session:{session_id}")
            except Exception:
                pass
