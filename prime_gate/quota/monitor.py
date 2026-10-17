from typing import Dict, Any, List, Optional
from ..config import MODELS_CATALOG

class QuotaMonitor:
    """Parses quota information, determines subscription tier, and resolves available models."""

    @staticmethod
    def detect_tier(account: Dict[str, Any]) -> str:
        """Determines whether account is on Google AI Pro (Trial) or (Paid) based on cached quota."""
        cached_quota = account.get("cachedQuota", {})
        claude_info = cached_quota.get("claude", {})
        model_count = claude_info.get("modelCount", 0)

        # In Antigravity:
        # modelCount: 2 on claude family indicates Sonnet 4.6 + Opus 4.6 (Trial / Partner Promo)
        # modelCount: 3+ or direct paid indicates Sonnet 5.5 + Opus 5.5 (Paid)
        if model_count == 2:
            return "google-ai-pro-trial"
        elif model_count > 2:
            return "google-ai-pro-paid"
        return "google-ai-pro-trial"

    @classmethod
    def get_tier_label(cls, account: Dict[str, Any]) -> str:
        tier = cls.detect_tier(account)
        if tier == "google-ai-pro-trial":
            return "Google AI Pro (Trial Tier)"
        return "Google AI Pro (Paid Tier)"

    @classmethod
    def get_available_models(cls, account: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not account:
            return MODELS_CATALOG["google-ai-pro-trial"]
        tier = cls.detect_tier(account)
        return MODELS_CATALOG.get(tier, MODELS_CATALOG["google-ai-pro-trial"])

    @staticmethod
    def parse_quota_details(account: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract clean quota rows for display in CLI and Web UI."""
        cached = account.get("cachedQuota", {})
        results = []

        families = [
            ("claude", "Claude Family (Sonnet/Opus 4.6 Thinking)"),
            ("gemini-flash", "Gemini Flash (Gemini 3.8 / 2.5 Flash)"),
            ("gemini-pro", "Gemini Pro (Gemini 2.5 Pro)"),
        ]

        for key, label in families:
            info = cached.get(key, {})
            remaining = info.get("remainingFraction", 1.0)
            reset_time = info.get("resetTime", "Active")
            pct = round(remaining * 100, 1)

            results.append({
                "family": key,
                "label": label,
                "percentage": pct,
                "reset_time": reset_time,
                "model_count": info.get("modelCount", 0)
            })

        return results
