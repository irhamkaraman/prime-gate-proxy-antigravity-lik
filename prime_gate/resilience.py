import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("prime_gate.resilience")

class AccountFailoverPool:
    """
    Manages account health, cooldowns, and automatic failovers to eliminate
    HTTP 429 (Rate Limit / Quota Exhaustion) errors from upstream Google Antigravity.
    """

    _cooldowns: Dict[str, float] = {}

    @classmethod
    def mark_rate_limited(cls, email: str, cooldown_seconds: int = 300):
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
    def get_failover_account(
        cls,
        current_email: str,
        accounts: List[Dict[str, Any]],
        quota_cache: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the best available candidate account excluding the current failing account.
        Prioritizes accounts not in cooldown, sorted by highest quota remaining if available.
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

        # Sort candidates by quota if available (highest remaining quota first)
        def _get_sort_score(acc):
            em = acc.get("email", "")
            if quota_cache and em in quota_cache:
                return quota_cache[em].get("remaining_fraction", 1.0)
            return 1.0

        candidates.sort(key=_get_sort_score, reverse=True)
        return candidates[0]

    @classmethod
    def get_ordered_accounts(
        cls,
        accounts: List[Dict[str, Any]],
        preferred_account: Optional[Dict[str, Any]] = None,
        quota_cache: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns a prioritized list of accounts for request execution.
        Healthy accounts (not in cooldown) are placed first, with preferred_account (if healthy)
        at the front. Quota remaining fraction is used to break ties among healthy accounts.
        Cooldown accounts are placed at the back, ordered by earliest recovery time.
        """
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
                return quota_cache[em].get("remaining_fraction", 1.0)
            return 1.0

        healthy.sort(key=_quota_score, reverse=True)
        cooling.sort(key=lambda a: cls._cooldowns.get(a.get("email", ""), 0))

        ordered = []
        if pref_email:
            pref_in_healthy = [a for a in healthy if a.get("email") == pref_email]
            if pref_in_healthy:
                ordered.append(pref_in_healthy[0])
                ordered.extend([a for a in healthy if a.get("email") != pref_email])
            else:
                ordered.extend(healthy)
        else:
            ordered.extend(healthy)

        for acc in cooling:
            if acc not in ordered:
                ordered.append(acc)

        return ordered if ordered else list(accounts)

