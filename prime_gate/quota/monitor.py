import time
import logging
import httpx
from typing import Dict, Any, List, Optional, Tuple
from ..config import MODELS_CATALOG, ANTIGRAVITY_ENDPOINT
from ..auth.oauth import get_access_token
from ..db import db, REC_MODEL, REC_QUOTA

logger = logging.getLogger("prime_gate.quota")

# Friendly labels for upstream Antigravity model identifiers
FRIENDLY_NAMES = {
    "claude-sonnet-4-6": "Claude Sonnet 4.6 (Thinking)",
    "claude-opus-4-6-thinking": "Claude Opus 4.6 (Thinking)",
    "gemini-3.8-flash": "Gemini 3.8 Flash (Recommended)",
    "gemini-3.8-flash-high": "Gemini 3.8 Flash High (Extended Thinking)",
    "gemini-3.8-flash-medium": "Gemini 3.8 Flash Medium",
    "gemini-3.8-flash-low": "Gemini 3.8 Flash Low",
    "gemini-3-flash": "Gemini 3 Flash",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
    "gemini-3.5-flash-low": "Gemini 3.5 Flash Low",
    "gemini-3.5-flash-extra-low": "Gemini 3.5 Flash Extra Low",
    "gemini-3.8-flash-tiered": "Gemini 3.8 Flash Tiered",
    "gemini-3-flash-agent": "Gemini 3 Flash Agent",
    "gpt-oss-120b-medium": "GPT-OSS 120B Medium",
    "gpt-oss-120b": "GPT-OSS 120B",
    "gemini-4-argon": "Gemini 4 Argon",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 (Thinking)",
    "claude-opus-5-5": "Claude Opus 5.5 (Thinking)"
}

class QuotaMonitor:
    """Parses quota information, queries live Antigravity models & quota, and resolves subscription tiers."""

    _models_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
    _quota_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}

    @staticmethod
    def detect_tier(account: Dict[str, Any]) -> str:
        """Determines whether account is on Google AI Pro (Trial) or (Paid) based on quota."""
        cached_quota = account.get("cachedQuota", {})
        claude_info = cached_quota.get("claude", {})
        model_count = claude_info.get("modelCount", 0)

        if model_count > 2:
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
        """
        Dynamically returns models catalog.
        Prioritizes live models stored in binary database from the user's Google Antigravity account,
        falling back to static defaults only if no account is configured.
        """
        email = account.get("email") if account else None
        if email:
            db_models = db.get(f"models:{email}")
            if db_models and db_models.get("models"):
                return db_models["models"]

        latest_models = db.get("models:latest")
        if latest_models and latest_models.get("models"):
            return latest_models["models"]

        if not account:
            return MODELS_CATALOG["google-ai-pro-trial"]
        tier = cls.detect_tier(account)
        return MODELS_CATALOG.get(tier, MODELS_CATALOG["google-ai-pro-trial"])

    @classmethod
    async def fetch_live_models_from_antigravity(
        cls, account: Dict[str, Any], force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """Directly queries Google Antigravity upstream for live supported models on the active account."""
        email = account.get("email", "default")
        now = time.time()

        if not force_refresh and email in cls._models_cache:
            cached_models, cached_time = cls._models_cache[email]
            if now - cached_time < 300:  # 5-minute cache TTL
                return cached_models

        try:
            token = await get_access_token(account)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "Antigravity/2.24.0.0"
            }
            payload = {"project": account.get("projectId")}

            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(
                    f"{ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels",
                    headers=headers,
                    json=payload
                )

                if resp.status_code == 200:
                    data = resp.json()
                    models_dict = data.get("models", {})
                    recommended_ids: List[str] = []
                    for sort in data.get("agentModelSorts", []):
                        for grp in sort.get("groups", []):
                            recommended_ids.extend(grp.get("modelIds", []))

                    # Gather all raw model keys
                    candidate_ids = list(dict.fromkeys(
                        recommended_ids +
                        list(models_dict.keys()) +
                        data.get("commandModelIds", [])
                    ))

                    # Filter out legacy/unavailable models (like gemini-2.5-*) and internal system models
                    clean_models: List[Dict[str, Any]] = []
                    seen = set()

                    # Add general gemini-3.8-flash alias first if recommended
                    if "gemini-3.8-flash-high" in candidate_ids or "gemini-3.8-flash-medium" in candidate_ids:
                        clean_models.append({
                            "id": "gemini-3.8-flash",
                            "name": FRIENDLY_NAMES.get("gemini-3.8-flash", "Gemini 3.8 Flash (Recommended)"),
                            "owned_by": "google-antigravity",
                            "provider": "prime gate proxy"
                        })
                        seen.add("gemini-3.8-flash")

                    for mid in candidate_ids:
                        if mid in seen:
                            continue
                        # Skip unavailable legacy 2.5 models and internal non-chat hooks
                        if "2.5" in mid or mid.startswith("chat_") or mid.startswith("tab_") or "image" in mid:
                            continue

                        name = FRIENDLY_NAMES.get(mid, mid)
                        clean_models.append({
                            "id": mid,
                            "name": name,
                            "owned_by": "google-antigravity",
                            "provider": "prime gate proxy"
                        })
                        seen.add(mid)

                    if clean_models:
                        cls._models_cache[email] = (clean_models, now)
                        db.set(f"models:{email}", {"models": clean_models, "timestamp": now}, REC_MODEL)
                        db.set("models:latest", {"models": clean_models, "timestamp": now}, REC_MODEL)
                        logger.info(f"Successfully loaded {len(clean_models)} live models directly from Google Antigravity for {email}")
                        return clean_models

        except Exception as e:
            logger.warning(f"Failed to fetch live models from Google Antigravity ({e}), checking binary DB snapshot.")

        # Check binary database fallback before static catalog
        db_cached = db.get(f"models:{email}") or db.get("models:latest")
        if db_cached and db_cached.get("models"):
            models_list = db_cached["models"]
            cls._models_cache[email] = (models_list, now)
            return models_list

        fallback = cls.get_available_models(account)
        cls._models_cache[email] = (fallback, now)
        return fallback

    @classmethod
    async def fetch_live_quota_from_antigravity(
        cls, account: Dict[str, Any], force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """Directly queries Google Antigravity upstream for live real-time quota telemetry."""
        email = account.get("email", "default")
        now = time.time()

        if not force_refresh and email in cls._quota_cache:
            cached_quota, cached_time = cls._quota_cache[email]
            if now - cached_time < 60:  # 1-minute quota cache TTL
                return cached_quota

        try:
            token = await get_access_token(account)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "Antigravity/2.24.0.0"
            }
            payload = {"project": account.get("projectId")}

            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(
                    f"{ANTIGRAVITY_ENDPOINT}/v1internal:retrieveUserQuotaSummary",
                    headers=headers,
                    json=payload
                )

                if resp.status_code == 200:
                    data = resp.json()
                    results: List[Dict[str, Any]] = []

                    for group in data.get("groups", []):
                        group_name = group.get("displayName", "Group")
                        for b in group.get("buckets", []):
                            b_id = b.get("bucketId", "")
                            disp = b.get("displayName", b_id)
                            rem = b.get("remainingFraction", 1.0)
                            reset = b.get("resetTime", "Active")
                            pct = round(rem * 100, 1)

                            results.append({
                                "family": b_id,
                                "label": f"{group_name} ({disp})",
                                "percentage": pct,
                                "reset_time": reset
                            })

                    if results:
                        cls._quota_cache[email] = (results, now)
                        db.set(f"quota:{email}", {"quota": results, "timestamp": now}, REC_QUOTA)
                        logger.info(f"Loaded live quota from Google Antigravity: {len(results)} quota buckets")
                        return results

        except Exception as e:
            logger.warning(f"Failed to fetch live quota from Google Antigravity ({e}), checking binary DB snapshot.")

        # Check binary database fallback before static parse
        db_quota = db.get(f"quota:{email}")
        if db_quota and db_quota.get("quota"):
            quota_list = db_quota["quota"]
            cls._quota_cache[email] = (quota_list, now)
            return quota_list

    @staticmethod
    def parse_quota_details(account: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback quota extraction from account metadata."""
        cached = account.get("cachedQuota", {})
        results = []

        families = [
            ("claude", "Claude Family (Sonnet/Opus 4.6 Thinking)"),
            ("gemini-flash", "Gemini Flash (Gemini 3.8 / 3.1 Flash)"),
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

    @classmethod
    async def get_models_health(
        cls, account: Optional[Dict[str, Any]], force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Computes comprehensive health status for all available models.
        Correlates live models, quota buckets, capacity limits, and capabilities.
        """
        if account:
            models = await cls.fetch_live_models_from_antigravity(account, force_refresh=force_refresh)
            quota_buckets = await cls.fetch_live_quota_from_antigravity(account, force_refresh=force_refresh)
        else:
            models = cls.get_available_models(None)
            quota_buckets = []

        # Map bucket family -> bucket data
        bucket_map = {b.get("family", "").lower(): b for b in quota_buckets}

        model_health_items: List[Dict[str, Any]] = []
        healthy_count = 0
        degraded_count = 0

        for m in models:
            mid = m.get("id", "")
            mid_lower = mid.lower()

            # Determine quota bucket family association
            family = "general"
            if "claude" in mid_lower:
                family = "claude"
            elif "flash" in mid_lower or "gemini" in mid_lower:
                family = "gemini-flash"
            elif "gpt" in mid_lower:
                family = "3p"

            # Match with quota buckets
            bucket = bucket_map.get(family)
            if not bucket:
                for b in quota_buckets:
                    if family in b.get("family", "").lower() or family in b.get("label", "").lower():
                        bucket = b
                        break

            quota_pct = bucket.get("percentage", 100.0) if bucket else 100.0
            reset_time = bucket.get("reset_time", "Active") if bucket else "Active"

            if quota_pct <= 0:
                status = "exhausted"
                degraded_count += 1
            elif quota_pct < 15.0:
                status = "degraded"
                degraded_count += 1
            else:
                status = "healthy"
                healthy_count += 1

            supports_thinking = any(k in mid_lower for k in ["thinking", "sonnet", "opus", "flash-high"])

            model_health_items.append({
                "id": mid,
                "name": m.get("name", mid),
                "status": status,
                "owned_by": m.get("owned_by", "google-antigravity"),
                "provider": "prime gate proxy",
                "family": family,
                "quota_percentage": quota_pct,
                "quota_reset": reset_time,
                "supports_thinking": supports_thinking,
                "supports_tools": True,
                "supports_streaming": True
            })

        overall_status = "healthy" if degraded_count == 0 else ("degraded" if healthy_count > 0 else "exhausted")
        if not account:
            overall_status = "unauthenticated"

        return {
            "status": overall_status,
            "total_models": len(model_health_items),
            "healthy_models": healthy_count,
            "degraded_models": degraded_count,
            "models": model_health_items
        }

