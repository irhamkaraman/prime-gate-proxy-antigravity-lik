import time
from typing import Optional, Dict, Tuple


class ThoughtSignatureCache:
    """
    Thread-safe in-memory TTL/LRU cache for Gemini 3 thought signatures.
    Maps call_id, function_name, or query hash to the upstream-issued base64 thought signature.
    Gemini 3 requires returning the exact thoughtSignature with functionCall parts in multi-turn conversations.
    """
    def __init__(self, maxsize: int = 2000, ttl_seconds: int = 7200):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def store(self, key: str, signature: Optional[str]) -> None:
        if not key or not signature:
            return
        # Avoid storing dummy signatures
        if signature == "skip_thought_signature_validator":
            return
        now = time.time()
        # Clean expired if cache exceeds capacity
        if len(self._cache) >= self._maxsize:
            expired = [k for k, (_, exp) in self._cache.items() if exp < now]
            for k in expired:
                self._cache.pop(k, None)
            if len(self._cache) >= self._maxsize:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                self._cache.pop(oldest_key, None)
        self._cache[key] = (signature, now + self._ttl)

    def get(self, key: str) -> Optional[str]:
        if not key:
            return None
        val = self._cache.get(key)
        if not val:
            return None
        sig, exp = val
        if time.time() > exp:
            self._cache.pop(key, None)
            return None
        return sig


# Global shared instance
thought_sig_cache = ThoughtSignatureCache()
