import time
import math
import logging
from collections import deque
from typing import Dict, Any, List, Optional
from .db import db, REC_SYSTEM

logger = logging.getLogger("prime_gate.telemetry")

DB_TELEMETRY_KEY = "system:token_telemetry"

class TokenTelemetryCollector:
    """
    High-performance in-memory and binary DB backed token telemetry engine.
    Aggregates token consumption across four granularities:
    - Per-second (last 60 seconds)
    - Per-minute (last 60 minutes)
    - Per-hour (last 24 hours)
    - Per-day (last 14 days)
    """

    def __init__(self):
        # Ring buffers for time-series aggregation
        # Format: timestamp_bucket -> {"prompt": X, "completion": Y, "reasoning": Z, "total": T, "requests": N}
        self.second_buckets: Dict[int, Dict[str, int]] = {}
        self.minute_buckets: Dict[int, Dict[str, int]] = {}
        self.hour_buckets: Dict[int, Dict[str, int]] = {}
        self.day_buckets: Dict[str, Dict[str, int]] = {}

        # Global counters
        self.total_tokens_all_time: int = 0
        self.total_requests_all_time: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_reasoning_tokens: int = 0
        self.latencies: deque = deque(maxlen=100)

        self._load_from_db()

    def _load_from_db(self):
        """Loads historical token totals and daily aggregates from compiled binary database."""
        try:
            persisted = db.get(DB_TELEMETRY_KEY)
            if persisted and isinstance(persisted, dict):
                self.total_tokens_all_time = persisted.get("total_tokens_all_time", 0)
                self.total_requests_all_time = persisted.get("total_requests_all_time", 0)
                self.total_prompt_tokens = persisted.get("total_prompt_tokens", 0)
                self.total_completion_tokens = persisted.get("total_completion_tokens", 0)
                self.total_reasoning_tokens = persisted.get("total_reasoning_tokens", 0)
                self.day_buckets = persisted.get("day_buckets", {})
                logger.info(f"Loaded telemetry: {self.total_tokens_all_time} tokens all-time from binary DB.")
        except Exception as e:
            logger.warning(f"Could not load telemetry from binary DB: {e}")

    def _persist_to_db(self):
        """Persists cumulative metrics and daily rollups into compiled binary database."""
        try:
            payload = {
                "total_tokens_all_time": self.total_tokens_all_time,
                "total_requests_all_time": self.total_requests_all_time,
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "total_reasoning_tokens": self.total_reasoning_tokens,
                "day_buckets": {k: v for k, v in list(self.day_buckets.items())[-30:]},
                "updated_at": time.time()
            }
            db.set(DB_TELEMETRY_KEY, payload, record_type=REC_SYSTEM)
        except Exception as e:
            logger.warning(f"Failed to persist telemetry to binary DB: {e}")

    def record_request(
        self,
        model: str = "default",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        latency_ms: float = 0.0,
        **kwargs
    ):
        """Backward-compatible alias for record_usage."""
        return self.record_usage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            latency_ms=latency_ms
        )

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int = 0,
        latency_ms: float = 0.0
    ):
        """Records a token usage event and updates all time-series ring buffers."""
        now = time.time()
        total = prompt_tokens + completion_tokens + reasoning_tokens

        self.total_tokens_all_time += total
        self.total_requests_all_time += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_reasoning_tokens += reasoning_tokens
        if latency_ms > 0:
            self.latencies.append(latency_ms)

        # 1. Second Bucket (Floor to second)
        sec_key = int(now)
        if sec_key not in self.second_buckets:
            self.second_buckets[sec_key] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0, "requests": 0}
        self.second_buckets[sec_key]["prompt"] += prompt_tokens
        self.second_buckets[sec_key]["completion"] += completion_tokens
        self.second_buckets[sec_key]["reasoning"] += reasoning_tokens
        self.second_buckets[sec_key]["total"] += total
        self.second_buckets[sec_key]["requests"] += 1

        # 2. Minute Bucket (Floor to minute)
        min_key = int(now // 60) * 60
        if min_key not in self.minute_buckets:
            self.minute_buckets[min_key] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0, "requests": 0}
        self.minute_buckets[min_key]["prompt"] += prompt_tokens
        self.minute_buckets[min_key]["completion"] += completion_tokens
        self.minute_buckets[min_key]["reasoning"] += reasoning_tokens
        self.minute_buckets[min_key]["total"] += total
        self.minute_buckets[min_key]["requests"] += 1

        # 3. Hour Bucket (Floor to hour)
        hour_key = int(now // 3600) * 3600
        if hour_key not in self.hour_buckets:
            self.hour_buckets[hour_key] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0, "requests": 0}
        self.hour_buckets[hour_key]["prompt"] += prompt_tokens
        self.hour_buckets[hour_key]["completion"] += completion_tokens
        self.hour_buckets[hour_key]["reasoning"] += reasoning_tokens
        self.hour_buckets[hour_key]["total"] += total
        self.hour_buckets[hour_key]["requests"] += 1

        # 4. Day Bucket (YYYY-MM-DD)
        day_key = time.strftime("%Y-%m-%d", time.localtime(now))
        if day_key not in self.day_buckets:
            self.day_buckets[day_key] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0, "requests": 0}
        self.day_buckets[day_key]["prompt"] += prompt_tokens
        self.day_buckets[day_key]["completion"] += completion_tokens
        self.day_buckets[day_key]["reasoning"] += reasoning_tokens
        self.day_buckets[day_key]["total"] += total
        self.day_buckets[day_key]["requests"] += 1

        # Prune old ring buffers
        cutoff_sec = int(now) - 120
        self.second_buckets = {k: v for k, v in self.second_buckets.items() if k >= cutoff_sec}

        cutoff_min = int(now) - 7200
        self.minute_buckets = {k: v for k, v in self.minute_buckets.items() if k >= cutoff_min}

        cutoff_hour = int(now) - (48 * 3600)
        self.hour_buckets = {k: v for k, v in self.hour_buckets.items() if k >= cutoff_hour}

        # Auto-persist every 5 requests
        if self.total_requests_all_time % 5 == 0:
            self._persist_to_db()

    def get_metrics(self, time_range: str = "1h") -> Dict[str, Any]:
        """
        Returns structured chart series and KPI summary for the selected time range.
        Options: '1h' (last 1 hour, 1m intervals - default), '1d' (last 24 hours, 1h intervals),
                 '7d' (last 7 days, 1d intervals), '1m' (last 1 month / 30 days, 1d intervals).
        """
        now = time.time()
        labels: List[str] = []
        prompt_series: List[int] = []
        completion_series: List[int] = []
        reasoning_series: List[int] = []
        total_series: List[int] = []

        # Normalize time_range identifier
        tr_norm = (time_range or "").strip().lower()
        if tr_norm in ["1h", "minute", "min", "1min", "60m", "hour_minute"]:
            target_range = "1h"
        elif tr_norm in ["1d", "day", "1day", "24h", "daily", "hour"]:
            target_range = "1d"
        elif tr_norm in ["7d", "week", "7day", "7days", "weekly"]:
            target_range = "7d"
        elif tr_norm in ["1m", "month", "1month", "30d", "monthly"]:
            target_range = "1m"
        else:
            target_range = "1h"

        # Pull historical hits from database to ensure no gaps across restarts
        db_records: List[Any] = []
        try:
            conn = db._get_connection()
            if target_range == "1h":
                min_ts = now - 3600
            elif target_range == "1d":
                min_ts = now - 86400
            elif target_range == "7d":
                min_ts = now - (7 * 86400)
            else:  # 1m (month)
                min_ts = now - (30 * 86400)

            cursor = conn.execute(
                "SELECT timestamp, prompt_tokens, completion_tokens, reasoning_tokens, total_tokens FROM pg_request_logs WHERE timestamp >= ?",
                (min_ts,)
            )
            db_records = cursor.fetchall()
        except Exception as e:
            logger.debug(f"Could not load request logs for telemetry aggregation: {e}")

        if target_range == "1h":
            # Last 60 minutes in 1-minute intervals (Default View)
            slot_map: Dict[int, Dict[str, int]] = {}
            for r in db_records:
                s = int(r["timestamp"] // 60) * 60
                if s not in slot_map:
                    slot_map[s] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0}
                slot_map[s]["prompt"] += r["prompt_tokens"]
                slot_map[s]["completion"] += r["completion_tokens"]
                slot_map[s]["reasoning"] += r["reasoning_tokens"]
                slot_map[s]["total"] += r["total_tokens"]

            for s, b in self.minute_buckets.items():
                if s not in slot_map:
                    slot_map[s] = dict(b)
                else:
                    slot_map[s]["prompt"] = max(slot_map[s]["prompt"], b.get("prompt", 0))
                    slot_map[s]["completion"] = max(slot_map[s]["completion"], b.get("completion", 0))
                    slot_map[s]["reasoning"] = max(slot_map[s]["reasoning"], b.get("reasoning", 0))
                    slot_map[s]["total"] = max(slot_map[s]["total"], b.get("total", 0))

            current_min = int(now // 60) * 60
            for m in range(current_min - (59 * 60), current_min + 60, 60):
                t_str = time.strftime("%H:%M", time.localtime(m))
                b = slot_map.get(m, {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0})
                labels.append(t_str)
                prompt_series.append(b["prompt"])
                completion_series.append(b["completion"])
                reasoning_series.append(b["reasoning"])
                total_series.append(b["total"])

        elif target_range == "1d":
            # Last 24 hours in 1-hour intervals
            hour_map: Dict[int, Dict[str, int]] = {}
            for r in db_records:
                h = int(r["timestamp"] // 3600) * 3600
                if h not in hour_map:
                    hour_map[h] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0}
                hour_map[h]["prompt"] += r["prompt_tokens"]
                hour_map[h]["completion"] += r["completion_tokens"]
                hour_map[h]["reasoning"] += r["reasoning_tokens"]
                hour_map[h]["total"] += r["total_tokens"]

            for h, b in self.hour_buckets.items():
                if h not in hour_map:
                    hour_map[h] = dict(b)
                else:
                    hour_map[h]["prompt"] = max(hour_map[h]["prompt"], b.get("prompt", 0))
                    hour_map[h]["completion"] = max(hour_map[h]["completion"], b.get("completion", 0))
                    hour_map[h]["reasoning"] = max(hour_map[h]["reasoning"], b.get("reasoning", 0))
                    hour_map[h]["total"] = max(hour_map[h]["total"], b.get("total", 0))

            current_hour = int(now // 3600) * 3600
            for h in range(current_hour - (23 * 3600), current_hour + 3600, 3600):
                t_str = time.strftime("%H:00", time.localtime(h))
                b = hour_map.get(h, {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0})
                labels.append(t_str)
                prompt_series.append(b["prompt"])
                completion_series.append(b["completion"])
                reasoning_series.append(b["reasoning"])
                total_series.append(b["total"])

        elif target_range == "7d":
            # Last 7 days in 1-day intervals
            day_map: Dict[str, Dict[str, int]] = {}
            for r in db_records:
                dk = time.strftime("%Y-%m-%d", time.localtime(r["timestamp"]))
                if dk not in day_map:
                    day_map[dk] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0}
                day_map[dk]["prompt"] += r["prompt_tokens"]
                day_map[dk]["completion"] += r["completion_tokens"]
                day_map[dk]["reasoning"] += r["reasoning_tokens"]
                day_map[dk]["total"] += r["total_tokens"]

            for dk, b in self.day_buckets.items():
                if dk not in day_map:
                    day_map[dk] = dict(b)
                else:
                    day_map[dk]["prompt"] = max(day_map[dk]["prompt"], b.get("prompt", 0))
                    day_map[dk]["completion"] = max(day_map[dk]["completion"], b.get("completion", 0))
                    day_map[dk]["reasoning"] = max(day_map[dk]["reasoning"], b.get("reasoning", 0))
                    day_map[dk]["total"] = max(day_map[dk]["total"], b.get("total", 0))

            current_day = int(now)
            for d in range(6, -1, -1):
                day_ts = current_day - (d * 86400)
                d_key = time.strftime("%Y-%m-%d", time.localtime(day_ts))
                d_label = time.strftime("%b %d", time.localtime(day_ts))
                b = day_map.get(d_key, {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0})
                labels.append(d_label)
                prompt_series.append(b["prompt"])
                completion_series.append(b["completion"])
                reasoning_series.append(b["reasoning"])
                total_series.append(b["total"])

        else:  # target_range == "1m" (1 month / 30 days)
            # Last 30 days in 1-day intervals
            month_map: Dict[str, Dict[str, int]] = {}
            for r in db_records:
                dk = time.strftime("%Y-%m-%d", time.localtime(r["timestamp"]))
                if dk not in month_map:
                    month_map[dk] = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0}
                month_map[dk]["prompt"] += r["prompt_tokens"]
                month_map[dk]["completion"] += r["completion_tokens"]
                month_map[dk]["reasoning"] += r["reasoning_tokens"]
                month_map[dk]["total"] += r["total_tokens"]

            for dk, b in self.day_buckets.items():
                if dk not in month_map:
                    month_map[dk] = dict(b)
                else:
                    month_map[dk]["prompt"] = max(month_map[dk]["prompt"], b.get("prompt", 0))
                    month_map[dk]["completion"] = max(month_map[dk]["completion"], b.get("completion", 0))
                    month_map[dk]["reasoning"] = max(month_map[dk]["reasoning"], b.get("reasoning", 0))
                    month_map[dk]["total"] = max(month_map[dk]["total"], b.get("total", 0))

            current_day = int(now)
            for d in range(29, -1, -1):
                day_ts = current_day - (d * 86400)
                d_key = time.strftime("%Y-%m-%d", time.localtime(day_ts))
                d_label = time.strftime("%b %d", time.localtime(day_ts))
                b = month_map.get(d_key, {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0})
                labels.append(d_label)
                prompt_series.append(b["prompt"])
                completion_series.append(b["completion"])
                reasoning_series.append(b["reasoning"])
                total_series.append(b["total"])

        # Calculate current real-time tokens per second (averaged over last 5 seconds)
        last_5_tokens = sum(self.second_buckets.get(int(now) - i, {}).get("total", 0) for i in range(5))
        current_tps = round(last_5_tokens / 5.0, 1)

        # Calculate today's total
        today_key = time.strftime("%Y-%m-%d", time.localtime(now))
        tokens_today = self.day_buckets.get(today_key, {}).get("total", 0)

        # Average latency
        avg_latency = round(sum(self.latencies) / len(self.latencies), 1) if self.latencies else 0.0

        return {
            "range": target_range,
            "summary": {
                "total_tokens_all_time": self.total_tokens_all_time,
                "total_requests_all_time": self.total_requests_all_time,
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "total_reasoning_tokens": self.total_reasoning_tokens,
                "current_tokens_per_sec": current_tps,
                "tokens_today": tokens_today,
                "avg_latency_ms": avg_latency
            },
            "chart_data": {
                "labels": labels,
                "prompt_tokens": prompt_series,
                "completion_tokens": completion_series,
                "reasoning_tokens": reasoning_series,
                "total_tokens": total_series
            }
        }


# Global Singleton Telemetry Collector
telemetry = TokenTelemetryCollector()
