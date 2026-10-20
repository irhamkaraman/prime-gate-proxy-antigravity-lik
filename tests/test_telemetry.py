import pytest
from prime_gate.telemetry import TokenTelemetryCollector


def test_telemetry_time_ranges():
    collector = TokenTelemetryCollector()
    
    # 1h: 60 data points (1-minute intervals)
    res_1h = collector.get_metrics("1h")
    assert res_1h["range"] == "1h"
    assert len(res_1h["chart_data"]["labels"]) == 60
    assert len(res_1h["chart_data"]["prompt_tokens"]) == 60
    assert len(res_1h["chart_data"]["total_tokens"]) == 60

    # 1d: 24 data points (1-hour intervals)
    res_1d = collector.get_metrics("1d")
    assert res_1d["range"] == "1d"
    assert len(res_1d["chart_data"]["labels"]) == 24
    assert len(res_1d["chart_data"]["total_tokens"]) == 24

    # 7d: 7 data points (1-day intervals)
    res_7d = collector.get_metrics("7d")
    assert res_7d["range"] == "7d"
    assert len(res_7d["chart_data"]["labels"]) == 7
    assert len(res_7d["chart_data"]["total_tokens"]) == 7

    # 1m: 30 data points (1-day intervals for 30 days)
    res_1m = collector.get_metrics("1m")
    assert res_1m["range"] == "1m"
    assert len(res_1m["chart_data"]["labels"]) == 30
    assert len(res_1m["chart_data"]["total_tokens"]) == 30


def test_telemetry_normalization():
    collector = TokenTelemetryCollector()
    # minute aliases default to 1h
    assert collector.get_metrics("minute")["range"] == "1h"
    assert collector.get_metrics("min")["range"] == "1h"
    
    # day aliases
    assert collector.get_metrics("day")["range"] == "1d"
    assert collector.get_metrics("24h")["range"] == "1d"
    
    # week aliases
    assert collector.get_metrics("week")["range"] == "7d"
    assert collector.get_metrics("weekly")["range"] == "7d"
    
    # month aliases
    assert collector.get_metrics("month")["range"] == "1m"
    assert collector.get_metrics("30d")["range"] == "1m"
    assert collector.get_metrics("1month")["range"] == "1m"
