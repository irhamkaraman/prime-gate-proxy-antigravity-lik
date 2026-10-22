#!/usr/bin/env python3
"""
Prime Gate Benchmark Suite
Measures proxy latency (p50/p95/p99), throughput (req/s), TTFT, and cache performance.
"""

import sys
import time
import math
import json
import argparse
import asyncio
from typing import List, Dict, Any, Optional

try:
    import httpx
except ImportError:
    print("Error: httpx is required for benchmarks. Run `pip install httpx`.")
    sys.exit(1)


def percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


async def run_worker(
    worker_id: int,
    queue: asyncio.Queue,
    results: List[Dict[str, Any]],
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    is_stream: bool
):
    while not queue.empty():
        try:
            req_idx = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        start_time = time.perf_counter()
        ttft = None
        status_code = 0
        error_msg = None
        token_count = 0

        try:
            if is_stream:
                async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
                    status_code = response.status_code
                    first_byte = True
                    async for chunk in response.aiter_raw():
                        if first_byte and len(chunk) > 0:
                            ttft = (time.perf_counter() - start_time) * 1000.0
                            first_byte = False
                        # approximate tokens
                        token_count += len(chunk) // 4
            else:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                status_code = response.status_code
                if status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    token_count = usage.get("total_tokens", len(response.text) // 4)

        except Exception as exc:
            error_msg = str(exc)
            status_code = 599

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        results.append({
            "worker_id": worker_id,
            "req_idx": req_idx,
            "duration_ms": duration_ms,
            "ttft_ms": ttft or duration_ms,
            "status_code": status_code,
            "token_count": token_count,
            "error": error_msg
        })
        queue.task_done()


async def run_benchmark(
    base_url: str,
    api_key: str,
    total_requests: int,
    concurrency: int,
    protocol: str,
    model: str,
    stream: bool
) -> Dict[str, Any]:
    if protocol == "anthropic":
        target_endpoint = f"{base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": model or "claude-3-7-sonnet",
            "max_tokens": 100,
            "stream": stream,
            "messages": [{"role": "user", "content": "Explain binary search in 2 sentences."}]
        }
    else:
        target_endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or "gemini-2.5-flash",
            "max_tokens": 100,
            "stream": stream,
            "messages": [{"role": "user", "content": "Explain binary search in 2 sentences."}]
        }

    queue: asyncio.Queue = asyncio.Queue()
    for i in range(total_requests):
        queue.put_nowait(i)

    results: List[Dict[str, Any]] = []
    bench_start = time.perf_counter()

    limits = httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        workers = [
            asyncio.create_task(run_worker(
                worker_id=w,
                queue=queue,
                results=results,
                client=client,
                url=target_endpoint,
                headers=headers,
                payload=payload,
                is_stream=stream
            ))
            for w in range(concurrency)
        ]
        await asyncio.gather(*workers)

    bench_total_s = time.perf_counter() - bench_start

    # Compute Statistics
    durations = [r["duration_ms"] for r in results if r["status_code"] == 200]
    ttfts = [r["ttft_ms"] for r in results if r["status_code"] == 200 and r.get("ttft_ms")]
    success_count = len(durations)
    failed_count = total_requests - success_count

    stats = {
        "protocol": protocol,
        "model": model,
        "streaming": stream,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "total_time_seconds": round(bench_total_s, 3),
        "throughput_req_per_sec": round(total_requests / bench_total_s, 2) if bench_total_s > 0 else 0,
        "success_rate_percent": round((success_count / total_requests) * 100, 2) if total_requests > 0 else 0,
        "latency_ms": {
            "min": round(min(durations), 2) if durations else 0,
            "mean": round(sum(durations) / len(durations), 2) if durations else 0,
            "p50": round(percentile(durations, 50), 2),
            "p90": round(percentile(durations, 90), 2),
            "p95": round(percentile(durations, 95), 2),
            "p99": round(percentile(durations, 99), 2),
            "max": round(max(durations), 2) if durations else 0,
        },
        "ttft_ms": {
            "p50": round(percentile(ttfts, 50), 2),
            "p95": round(percentile(ttfts, 95), 2),
            "p99": round(percentile(ttfts, 99), 2),
        } if stream else None
    }
    return stats


def print_stats(stats: Dict[str, Any]):
    print("\n" + "=" * 65)
    print(" " * 20 + "PRIME GATE BENCHMARK REPORT")
    print("=" * 65)
    print(f" Protocol:        {stats['protocol'].upper()}")
    print(f" Target Model:    {stats['model']}")
    print(f" Mode:            {'Streaming (SSE)' if stats['streaming'] else 'Non-Streaming'}")
    print(f" Concurrency:     {stats['concurrency']} workers")
    print(f" Total Requests:  {stats['total_requests']}")
    print(f" Wall Time:       {stats['total_time_seconds']} s")
    print(f" Throughput:      {stats['throughput_req_per_sec']} req/s")
    print(f" Success Rate:    {stats['success_rate_percent']}%")
    print("-" * 65)
    print(" LATENCY DISTRIBUTION (ms)")
    lat = stats["latency_ms"]
    print(f"   Min:   {lat['min']:>8.2f} ms    |   p50:   {lat['p50']:>8.2f} ms")
    print(f"   Mean:  {lat['mean']:>8.2f} ms    |   p95:   {lat['p95']:>8.2f} ms")
    print(f"   Max:   {lat['max']:>8.2f} ms    |   p99:   {lat['p99']:>8.2f} ms")
    if stats.get("ttft_ms"):
        tt = stats["ttft_ms"]
        print("-" * 65)
        print(" TIME TO FIRST TOKEN (TTFT - ms)")
        print(f"   p50:   {tt['p50']:>8.2f} ms    |   p95:   {tt['p95']:>8.2f} ms    |   p99:   {tt['p99']:>8.2f} ms")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Prime Gate Latency & Throughput Benchmark")
    parser.add_argument("--url", default="http://127.0.0.1:52111", help="Base URL of Prime Gate proxy")
    parser.add_argument("--api-key", default="pg-live-default-benchmark-key", help="API key")
    parser.add_argument("-n", "--requests", type=int, default=20, help="Number of total requests")
    parser.add_argument("-c", "--concurrency", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--protocol", choices=["openai", "anthropic"], default="openai", help="Protocol")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Model name")
    parser.add_argument("--stream", action="store_true", help="Enable SSE streaming mode")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of ASCII table")

    args = parser.parse_args()

    stats = asyncio.run(run_benchmark(
        base_url=args.url,
        api_key=args.api_key,
        total_requests=args.requests,
        concurrency=args.concurrency,
        protocol=args.protocol,
        model=args.model,
        stream=args.stream
    ))

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print_stats(stats)


if __name__ == "__main__":
    main()
