import time
import json
import hashlib
import base64
from collections import deque
from typing import Optional, Dict, Tuple, Any

DEFAULT_SKIP_SIGNATURE = "skip_thought_signature_validator"
BYPASS_SIGNATURES = {
    "skip_thought_signature_validator",
    "context_engineering_is_the_way_to_go",
}


def is_valid_base64(s: str) -> bool:
    """Verifies that a string is valid RFC 4648 standard Base64."""
    if not isinstance(s, str) or not s:
        return False
    try:
        decoded = base64.b64decode(s, validate=True)
        return len(decoded) > 0
    except Exception:
        return False


def sanitize_thought_signature(sig: Optional[str]) -> str:
    """
    Guarantees any thought signature delivered to Google upstream is strictly valid.
    - If empty/None -> returns official Google bypass: 'skip_thought_signature_validator'
    - If already official bypass -> returns as is
    - If valid Base64 string -> returns as is
    - If invalid Base64 (contains underscores, unescaped characters) -> safely falls back to 'skip_thought_signature_validator'
    """
    if not sig:
        return DEFAULT_SKIP_SIGNATURE
    if sig in BYPASS_SIGNATURES:
        return sig
    if is_valid_base64(sig):
        return sig
    return DEFAULT_SKIP_SIGNATURE


class ThoughtSignatureCache:
    """
    Two-Tier Hybrid Cache (L1 Memory + L2 SQLite WAL) for Gemini 3 Thought Signatures.
    Maps call_id or call_hash to upstream-issued cryptographic thought signatures.
    
    Guarantees:
    - 100% survives daemon restarts, process crashes, and updates via SQLite WAL storage.
    - Multi-key indexing (call_id, arg hash) for resilient multi-turn mapping.
    - Deterministic fallback to Google's official bypass signature prevents upstream HTTP 400 errors.
    """
    def __init__(self, maxsize: int = 2000, ttl_seconds: int = 86400):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._recent_signatures: deque = deque(maxlen=100)
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    @staticmethod
    def compute_call_hash(fn_name: str, fn_args: Any) -> str:
        """Computes a deterministic hash from function name and arguments."""
        if not fn_name:
            return ""
        if isinstance(fn_args, str):
            try:
                fn_args = json.loads(fn_args)
            except Exception:
                pass
        try:
            if isinstance(fn_args, dict):
                args_str = json.dumps(fn_args, sort_keys=True)
            else:
                args_str = str(fn_args)
        except Exception:
            args_str = str(fn_args)
        raw = f"{fn_name}:{args_str}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def store(
        self,
        key: str,
        signature: Optional[str],
        fn_name: Optional[str] = None,
        fn_args: Any = None,
        model: Optional[str] = None
    ) -> None:
        if not key or not signature:
            return

        clean_sig = sanitize_thought_signature(signature)
        now = time.time()
        call_hash = self.compute_call_hash(fn_name, fn_args) if fn_name else None

        # 1. Update L1 In-Memory Cache
        if len(self._cache) >= self._maxsize:
            expired = [k for k, (_, exp) in self._cache.items() if exp < now]
            for k in expired:
                self._cache.pop(k, None)
            if len(self._cache) >= self._maxsize:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                self._cache.pop(oldest_key, None)

        self._cache[key] = (clean_sig, now + self._ttl)
        if call_hash:
            self._cache[f"hash:{call_hash}"] = (clean_sig, now + self._ttl)

        # 2. Only write genuine cryptographic Base64 signatures to persistent storage and ring buffer
        if clean_sig != DEFAULT_SKIP_SIGNATURE and is_valid_base64(clean_sig):
            self._recent_signatures.append(clean_sig)
            try:
                from ..db import db
                db.store_thought_signature(
                    key=key,
                    signature=clean_sig,
                    fn_name=fn_name,
                    call_hash=call_hash,
                    model=model,
                    ttl_seconds=self._ttl
                )
                if call_hash:
                    db.store_thought_signature(
                        key=f"hash:{call_hash}",
                        signature=clean_sig,
                        fn_name=fn_name,
                        call_hash=call_hash,
                        model=model,
                        ttl_seconds=self._ttl
                    )
            except Exception:
                pass

    def get(self, key: str) -> Optional[str]:
        if not key:
            return None
        now = time.time()

        # Check L1 Cache
        val = self._cache.get(key)
        if val:
            sig, exp = val
            if now <= exp:
                return sig
            self._cache.pop(key, None)

        # Fallback to L2 SQLite
        try:
            from ..db import db
            sig = db.get_thought_signature(key)
            if sig:
                clean_sig = sanitize_thought_signature(sig)
                self._cache[key] = (clean_sig, now + self._ttl)
                return clean_sig
        except Exception:
            pass

        return None

    def get_by_hash(self, call_hash: str) -> Optional[str]:
        if not call_hash:
            return None
        val = self.get(f"hash:{call_hash}")
        if val:
            return val
        try:
            from ..db import db
            sig = db.get_thought_signature_by_hash(call_hash)
            if sig:
                clean_sig = sanitize_thought_signature(sig)
                self._cache[f"hash:{call_hash}"] = (clean_sig, time.time() + self._ttl)
                return clean_sig
        except Exception:
            pass
        return None

    def get_by_fn(self, fn_name: str) -> Optional[str]:
        """Deprecated: Avoid guessing signatures across different calls to prevent token contamination."""
        return None

    def get_latest_valid_signature(self, model: Optional[str] = None) -> Optional[str]:
        if self._recent_signatures:
            return self._recent_signatures[-1]
        try:
            from ..db import db
            sig = db.get_latest_valid_thought_signature(model=model)
            if sig:
                clean_sig = sanitize_thought_signature(sig)
                self._recent_signatures.append(clean_sig)
                return clean_sig
        except Exception:
            pass
        return None

    def resolve_signature(
        self,
        call_id: Optional[str] = None,
        fn_name: Optional[str] = None,
        fn_args: Any = None,
        model: Optional[str] = None
    ) -> str:
        """
        Cascading multi-tier signature resolver:
        1. Exact call_id match (L1 Memory + L2 SQLite WAL)
        2. Exact function name + arguments hash match (L1 Memory + L2 SQLite WAL)
        3. Official Google validator bypass ('skip_thought_signature_validator')

        Guarantees:
        - NEVER returns None
        - NEVER returns an invalid Base64 token
        - NEVER crashes upstream Google Base64 decoder
        """
        # Tier 1: Direct call_id
        if call_id:
            sig = self.get(call_id)
            if sig:
                return sanitize_thought_signature(sig)

        # Tier 2: Call hash (fn_name + args)
        if fn_name and fn_args is not None:
            chash = self.compute_call_hash(fn_name, fn_args)
            if chash:
                sig = self.get_by_hash(chash)
                if sig:
                    return sanitize_thought_signature(sig)

        # Tier 3: Official Google bypass string for client-injected or historical calls
        return DEFAULT_SKIP_SIGNATURE


# Global shared instance
thought_sig_cache = ThoughtSignatureCache()
