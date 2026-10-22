import time
import threading
from typing import Dict, Tuple, Optional, List

class PrometheusMetrics:
    """
    In-memory Prometheus exposition metric collector for Prime Gate.
    Tracks HTTP requests, latencies, time-to-first-token (TTFT), token consumption,
    cache efficiency, account failovers, and compactor savings with zero third-party dependencies.
    """

    DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
    TTFT_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)

    def __init__(self):
        self._lock = threading.Lock()
        
        # (protocol, model, status) -> count
        self._requests: Dict[Tuple[str, str, int], int] = {}
        
        # Duration histograms: (protocol, model) -> {bucket: count}
        self._duration_buckets: Dict[Tuple[str, str], Dict[float, int]] = {}
        self._duration_sums: Dict[Tuple[str, str], float] = {}
        self._duration_counts: Dict[Tuple[str, str], int] = {}
        
        # TTFT histograms: (protocol, model) -> {bucket: count}
        self._ttft_buckets: Dict[Tuple[str, str], Dict[float, int]] = {}
        self._ttft_sums: Dict[Tuple[str, str], float] = {}
        self._ttft_counts: Dict[Tuple[str, str], int] = {}
        
        # Token counters by type
        self._tokens: Dict[str, int] = {
            "prompt": 0,
            "completion": 0,
            "reasoning": 0,
            "saved": 0
        }
        
        # Cache counters
        self._cache_hits: Dict[str, int] = {
            "exact": 0,
            "semantic": 0
        }
        self._cache_misses: int = 0
        
        # Resiliency & state metrics
        self._active_accounts: int = 0
        self._account_failovers: int = 0
        self._compactor_tokens_saved: int = 0

    def record_request(
        self,
        protocol: str,
        model: str,
        status: int,
        duration_seconds: float,
        ttft_seconds: Optional[float] = None
    ):
        """Records an API request duration, status code, and optional TTFT."""
        protocol = protocol or "unknown"
        model = model or "unknown"
        key = (protocol, model, int(status))
        hist_key = (protocol, model)

        with self._lock:
            self._requests[key] = self._requests.get(key, 0) + 1
            
            # Duration histogram
            if hist_key not in self._duration_buckets:
                self._duration_buckets[hist_key] = {b: 0 for b in self.DURATION_BUCKETS}
                self._duration_sums[hist_key] = 0.0
                self._duration_counts[hist_key] = 0
            
            self._duration_sums[hist_key] += duration_seconds
            self._duration_counts[hist_key] += 1
            for b in self.DURATION_BUCKETS:
                if duration_seconds <= b:
                    self._duration_buckets[hist_key][b] += 1

            # TTFT histogram
            if ttft_seconds is not None and ttft_seconds >= 0:
                if hist_key not in self._ttft_buckets:
                    self._ttft_buckets[hist_key] = {b: 0 for b in self.TTFT_BUCKETS}
                    self._ttft_sums[hist_key] = 0.0
                    self._ttft_counts[hist_key] = 0
                
                self._ttft_sums[hist_key] += ttft_seconds
                self._ttft_counts[hist_key] += 1
                for b in self.TTFT_BUCKETS:
                    if ttft_seconds <= b:
                        self._ttft_buckets[hist_key][b] += 1

    def record_tokens(self, prompt: int = 0, completion: int = 0, reasoning: int = 0, saved: int = 0):
        with self._lock:
            self._tokens["prompt"] += max(0, prompt)
            self._tokens["completion"] += max(0, completion)
            self._tokens["reasoning"] += max(0, reasoning)
            self._tokens["saved"] += max(0, saved)

    def record_cache_hit(self, hit_type: str = "exact"):
        with self._lock:
            t = hit_type if hit_type in self._cache_hits else "exact"
            self._cache_hits[t] += 1

    def record_cache_miss(self):
        with self._lock:
            self._cache_misses += 1

    def record_failover(self):
        with self._lock:
            self._account_failovers += 1

    def record_compactor_saved(self, tokens: int):
        with self._lock:
            self._compactor_tokens_saved += max(0, tokens)

    def set_active_accounts(self, count: int):
        with self._lock:
            self._active_accounts = max(0, count)

    def render_prometheus_text(self) -> str:
        """Formats all registered metrics into Prometheus text format."""
        lines: List[str] = []

        with self._lock:
            # 1. primegate_requests_total
            lines.append("# HELP primegate_requests_total Total number of API proxy requests processed.")
            lines.append("# TYPE primegate_requests_total counter")
            if not self._requests:
                lines.append('primegate_requests_total{protocol="all",model="none",status="200"} 0')
            else:
                for (proto, model, st), val in sorted(self._requests.items()):
                    lines.append(f'primegate_requests_total{{protocol="{proto}",model="{model}",status="{st}"}} {val}')

            # 2. primegate_request_duration_seconds
            lines.append("# HELP primegate_request_duration_seconds Latency of API proxy requests in seconds.")
            lines.append("# TYPE primegate_request_duration_seconds histogram")
            for (proto, model), buckets in sorted(self._duration_buckets.items()):
                for b in self.DURATION_BUCKETS:
                    lines.append(f'primegate_request_duration_seconds_bucket{{protocol="{proto}",model="{model}",le="{b}"}} {buckets[b]}')
                lines.append(f'primegate_request_duration_seconds_bucket{{protocol="{proto}",model="{model}",le="+Inf"}} {self._duration_counts[(proto, model)]}')
                lines.append(f'primegate_request_duration_seconds_sum{{protocol="{proto}",model="{model}"}} {self._duration_sums[(proto, model)]:.6f}')
                lines.append(f'primegate_request_duration_seconds_count{{protocol="{proto}",model="{model}"}} {self._duration_counts[(proto, model)]}')

            # 3. primegate_time_to_first_token_seconds
            lines.append("# HELP primegate_time_to_first_token_seconds Time to first token for streaming responses in seconds.")
            lines.append("# TYPE primegate_time_to_first_token_seconds histogram")
            for (proto, model), buckets in sorted(self._ttft_buckets.items()):
                for b in self.TTFT_BUCKETS:
                    lines.append(f'primegate_time_to_first_token_seconds_bucket{{protocol="{proto}",model="{model}",le="{b}"}} {buckets[b]}')
                lines.append(f'primegate_time_to_first_token_seconds_bucket{{protocol="{proto}",model="{model}",le="+Inf"}} {self._ttft_counts[(proto, model)]}')
                lines.append(f'primegate_time_to_first_token_seconds_sum{{protocol="{proto}",model="{model}"}} {self._ttft_sums[(proto, model)]:.6f}')
                lines.append(f'primegate_time_to_first_token_seconds_count{{protocol="{proto}",model="{model}"}} {self._ttft_counts[(proto, model)]}')

            # 4. primegate_tokens_total
            lines.append("# HELP primegate_tokens_total Total tokens processed and saved.")
            lines.append("# TYPE primegate_tokens_total counter")
            for token_type, count in self._tokens.items():
                lines.append(f'primegate_tokens_total{{type="{token_type}"}} {count}')

            # 5. primegate_cache_hits_total & primegate_cache_misses_total
            lines.append("# HELP primegate_cache_hits_total Total number of cache hits.")
            lines.append("# TYPE primegate_cache_hits_total counter")
            for hit_type, count in self._cache_hits.items():
                lines.append(f'primegate_cache_hits_total{{type="{hit_type}"}} {count}')

            lines.append("# HELP primegate_cache_misses_total Total number of cache misses.")
            lines.append("# TYPE primegate_cache_misses_total counter")
            lines.append(f'primegate_cache_misses_total {self._cache_misses}')

            # 6. primegate_active_accounts
            lines.append("# HELP primegate_active_accounts Number of active ready upstream accounts.")
            lines.append("# TYPE primegate_active_accounts gauge")
            lines.append(f'primegate_active_accounts {self._active_accounts}')

            # 7. primegate_account_failovers_total
            lines.append("# HELP primegate_account_failovers_total Total automatic upstream account failovers triggered.")
            lines.append("# TYPE primegate_account_failovers_total counter")
            lines.append(f'primegate_account_failovers_total {self._account_failovers}')

            # 8. primegate_compactor_tokens_saved_total
            lines.append("# HELP primegate_compactor_tokens_saved_total Total prompt tokens saved by Agent Context Compactor.")
            lines.append("# TYPE primegate_compactor_tokens_saved_total counter")
            lines.append(f'primegate_compactor_tokens_saved_total {self._compactor_tokens_saved}')

        return "\n".join(lines) + "\n"

# Global singleton instance
metrics = PrometheusMetrics()
