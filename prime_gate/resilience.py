import time
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

logger = logging.getLogger("prime_gate.resilience")

class AccountFailoverPool:
    """
    Manages account health, cooldowns, in-flight concurrency, and automatic failovers
    to eliminate HTTP 429 (Rate Limit / Quota Exhaustion) errors from upstream Google Antigravity.
    """

    _cooldowns: Dict[str, float] = {}
    _in_flight: Dict[str, int] = {}

    @classmethod
    def mark_rate_limited(cls, email: str, cooldown_seconds: int = 6):
        """Places an account in cooldown after an upstream 429 response."""
        cls._cooldowns[email] = time.time() + cooldown_seconds
        logger.warning(
            f"[FAILOVER] Account {email} placed in cooldown for {cooldown_seconds}s due to upstream rate limit."
        )

    @classmethod
    def is_available(cls, account: Dict[str, Any]) -> bool:
        """Returns True if the account is not currently in cooldown."""
        email = account.get("email", "")
        if not email:
            return False
        expiry = cls._cooldowns.get(email, 0)
        return time.time() > expiry

    @classmethod
    def acquire(cls, email: str):
        """Track that an account has an active in-flight request."""
        if email:
            cls._in_flight[email] = cls._in_flight.get(email, 0) + 1
            logger.info(f"[CONCURRENCY] Account {email} acquired (in-flight: {cls._in_flight[email]})")

    @classmethod
    def release(cls, email: str):
        """Release the in-flight tracking for an account."""
        if email and email in cls._in_flight:
            cls._in_flight[email] = max(0, cls._in_flight[email] - 1)
            logger.info(f"[CONCURRENCY] Account {email} released (in-flight: {cls._in_flight[email]})")

    @classmethod
    def get_in_flight(cls, email: str) -> int:
        return cls._in_flight.get(email, 0)

    @classmethod
    def get_total_in_flight(cls) -> int:
        """Returns the total number of in-flight requests across all accounts."""
        return sum(cls._in_flight.values())

    @classmethod
    @asynccontextmanager
    async def slot(cls, email: str):
        """Async context manager ensuring in-flight count is always cleaned up."""
        cls.acquire(email)
        try:
            yield
        finally:
            cls.release(email)

    @classmethod
    def get_failover_account(
        cls,
        current_email: str,
        accounts: List[Dict[str, Any]],
        quota_cache: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the best available candidate account excluding the current failing account.
        Prioritizes accounts not in cooldown, with 0 in-flight requests, sorted by highest quota remaining.
        """
        candidates = [
            acc for acc in accounts
            if acc.get("email") != current_email and cls.is_available(acc)
        ]
        if not candidates:
            # Fallback: if all accounts are cooled down, pick the one with earliest cooldown expiry
            other_accs = [acc for acc in accounts if acc.get("email") != current_email]
            if other_accs:
                other_accs.sort(key=lambda a: cls._cooldowns.get(a.get("email", ""), 0))
                return other_accs[0]
            return None

        def _get_sort_score(acc):
            em = acc.get("email", "")
            in_fl = cls.get_in_flight(em)
            q_score = 1.0
            if quota_cache and em in quota_cache:
                q_val = quota_cache[em]
                if isinstance(q_val, dict):
                    q_score = q_val.get("remaining_fraction", 1.0)
                elif isinstance(q_val, list) and q_val:
                    pcts = [b.get("percentage", 100) for b in q_val if isinstance(b, dict)]
                    q_score = (sum(pcts) / len(pcts)) / 100.0 if pcts else 1.0
            # Prioritize 0 in-flight accounts first, then highest quota
            return (-in_fl, q_score)

        candidates.sort(key=_get_sort_score, reverse=True)
        return candidates[0]

    @classmethod
    def get_ordered_accounts(
        cls,
        accounts: List[Dict[str, Any]],
        preferred_account: Optional[Dict[str, Any]] = None,
        quota_cache: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Returns a prioritized, load-balanced list of accounts for request execution.
        1. Healthy accounts (not in cooldown) are placed first.
        2. Among healthy accounts, accounts with FEWER in-flight requests are placed first.
        3. If multiple accounts have 0 in-flight requests, preferred_account (if healthy & idle)
           comes first, followed by highest remaining quota.
        4. Cooldown accounts are placed at the back, ordered by earliest recovery time.
        """
        if not preferred_account and "active_account" in kwargs:
            preferred_account = kwargs["active_account"]
        if not accounts:
            return []

        pref_email = preferred_account.get("email") if preferred_account else None

        healthy = []
        cooling = []

        for acc in accounts:
            if cls.is_available(acc):
                healthy.append(acc)
            else:
                cooling.append(acc)

        def _quota_score(acc):
            em = acc.get("email", "")
            if quota_cache and em in quota_cache:
                q_val = quota_cache[em]
                if isinstance(q_val, dict):
                    return q_val.get("remaining_fraction", 1.0)
                elif isinstance(q_val, list) and q_val:
                    pcts = [b.get("percentage", 100) for b in q_val if isinstance(b, dict)]
                    return (sum(pcts) / len(pcts)) / 100.0 if pcts else 1.0
            return 1.0

        def _healthy_sort_key(acc):
            em = acc.get("email", "")
            in_fl = cls.get_in_flight(em)
            is_pref = 1 if (em == pref_email and in_fl == 0) else 0
            q_score = _quota_score(acc)
            # Tier 1: In-flight count (0 in-flight first)
            # Tier 2: Preferred account if idle
            # Tier 3: Highest remaining quota
            return (-in_fl, is_pref, q_score)

        healthy.sort(key=_healthy_sort_key, reverse=True)
        cooling.sort(key=lambda a: cls._cooldowns.get(a.get("email", ""), 0))

        ordered = list(healthy)
        for acc in cooling:
            if acc not in ordered:
                ordered.append(acc)

        return ordered if ordered else list(accounts)

