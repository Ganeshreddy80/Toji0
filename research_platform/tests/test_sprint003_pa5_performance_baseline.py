"""Sprint 003 — PA-5 Empirical Performance Baseline Test & Utility Suite.

Measures process_tick() latency (p50, p95, p99, max), throughput (ticks/sec),
CPU utilization, RSS memory, and event generation rates across 1, 2, 5, and 10 active symbols.
PA-5 is MEASURE ONLY — zero production code changes.
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import psutil
import pytest
from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.price_action.repository import PriceActionRepository


# ---------------------------------------------------------------------------
# BENCHMARK TICK STREAM GENERATOR
# ---------------------------------------------------------------------------

def generate_multi_symbol_ticks(
    symbols: List[str],
    ticks_per_symbol: int = 2000,
    start_time: datetime | None = None,
    seed: int = 42
) -> List[Tuple[str, float, datetime, float]]:
    """Generates interleaved tick streams across multiple symbols for realistic gateway simulation."""
    if start_time is None:
        start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    all_ticks: List[Tuple[str, float, datetime, float]] = []

    for s_idx, sym in enumerate(symbols):
        base_price = 1000.0 * (s_idx + 1)
        for i in range(ticks_per_symbol):
            ts = start_time + timedelta(seconds=i * 15)
            # Deterministic price wave pattern
            price = base_price + (math.sin((i + s_idx * 10) / 20.0) * 50.0)
            vol = 10.0 + abs(math.cos(i / 10.0)) * 5.0
            all_ticks.append((sym, price, ts, vol))

    # Interleave ticks by timestamp order to simulate multi-symbol gateway arrival
    all_ticks.sort(key=lambda x: x[2])
    return all_ticks


def run_scaling_benchmark(
    symbols: List[str],
    ticks_per_symbol: int,
    warmup_ticks: int = 500
) -> Dict[str, Any]:
    """Executes a single scaling benchmark run, recording timing, memory, and throughput metrics."""
    process = psutil.Process(os.getpid())

    # 1. Warm-up Phase
    warmup_data = generate_multi_symbol_ticks(symbols, ticks_per_symbol=warmup_ticks // len(symbols) + 1)[:warmup_ticks]
    event_bus_warmup = MagicMock()
    orch_warmup = PriceActionOrchestrator(event_bus=event_bus_warmup, repository=PriceActionRepository())

    for sym, price, ts, vol in warmup_data:
        orch_warmup.process_tick(sym, price, ts, vol)

    # 2. Main Benchmark Setup
    event_bus = MagicMock()
    orch = PriceActionOrchestrator(event_bus=event_bus, repository=PriceActionRepository())
    ticks = generate_multi_symbol_ticks(symbols, ticks_per_symbol=ticks_per_symbol)
    total_ticks = len(ticks)

    latencies_us: List[float] = []

    # Initial system metrics
    rss_before_mb = process.memory_info().rss / (1024 * 1024)
    process.cpu_percent(interval=None)  # Reset CPU measurement window
    wall_start = time.perf_counter()

    # 3. Execution Loop with Microsecond Timing Isolation
    for sym, price, ts, vol in ticks:
        t0 = time.perf_counter_ns()
        orch.process_tick(sym, price, ts, vol)
        t1 = time.perf_counter_ns()
        latencies_us.append((t1 - t0) / 1000.0)

    wall_end = time.perf_counter()
    cpu_usage_pct = process.cpu_percent(interval=None)
    rss_after_mb = process.memory_info().rss / (1024 * 1024)

    total_wall_sec = wall_end - wall_start
    tps = total_ticks / total_wall_sec if total_wall_sec > 0 else 0.0

    # Sort latencies for percentile calculation
    latencies_us.sort()
    p50 = latencies_us[int(0.50 * total_ticks)]
    p95 = latencies_us[int(0.95 * total_ticks)]
    p99 = latencies_us[int(0.99 * total_ticks)]
    max_lat = latencies_us[-1]
    avg_lat = sum(latencies_us) / total_ticks

    events_published = event_bus.publish.call_count
    events_per_1000 = (events_published / total_ticks) * 1000.0 if total_ticks > 0 else 0.0

    return {
        "symbol_count": len(symbols),
        "tick_count": total_ticks,
        "p50_us": round(p50, 2),
        "p95_us": round(p95, 2),
        "p99_us": round(p99, 2),
        "max_us": round(max_lat, 2),
        "avg_us": round(avg_lat, 2),
        "ticks_per_second": round(tps, 2),
        "cpu_percent": round(cpu_usage_pct, 2),
        "rss_memory_mb": round(rss_after_mb, 2),
        "rss_delta_mb": round(rss_after_mb - rss_before_mb, 2),
        "events_published": events_published,
        "events_per_1000_ticks": round(events_per_1000, 2),
        "total_wall_sec": round(total_wall_sec, 4),
    }


# ---------------------------------------------------------------------------
# PYTEST BENCHMARK EXECUTIONS
# ---------------------------------------------------------------------------

def test_pa5_scaling_matrix_1_symbol() -> None:
    """Benchmark Scaling Matrix 1: 1 symbol (10,000 ticks)."""
    res = run_scaling_benchmark(symbols=["BTCUSDT"], ticks_per_symbol=10000)
    print(f"\n--- PA-5 Scaling Benchmark: 1 Symbol ---")
    print(json.dumps(res, indent=2))
    assert res["tick_count"] == 10000
    assert res["p50_us"] > 0
    assert res["ticks_per_second"] > 1000.0


def test_pa5_scaling_matrix_2_symbols() -> None:
    """Benchmark Scaling Matrix 2: 2 symbols (5,000 ticks/symbol = 10,000 total)."""
    res = run_scaling_benchmark(symbols=["BTCUSDT", "ETHUSDT"], ticks_per_symbol=5000)
    print(f"\n--- PA-5 Scaling Benchmark: 2 Symbols ---")
    print(json.dumps(res, indent=2))
    assert res["tick_count"] == 10000
    assert res["p50_us"] > 0
    assert res["ticks_per_second"] > 1000.0


def test_pa5_scaling_matrix_5_symbols() -> None:
    """Benchmark Scaling Matrix 3: 5 symbols (2,000 ticks/symbol = 10,000 total)."""
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
    res = run_scaling_benchmark(symbols=symbols, ticks_per_symbol=2000)
    print(f"\n--- PA-5 Scaling Benchmark: 5 Symbols ---")
    print(json.dumps(res, indent=2))
    assert res["tick_count"] == 10000
    assert res["p50_us"] > 0
    assert res["ticks_per_second"] > 1000.0


def test_pa5_scaling_matrix_10_symbols() -> None:
    """Benchmark Scaling Matrix 4: 10 symbols (1,000 ticks/symbol = 10,000 total)."""
    symbols = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
        "XRPUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "LINKUSDT"
    ]
    res = run_scaling_benchmark(symbols=symbols, ticks_per_symbol=1000)
    print(f"\n--- PA-5 Scaling Benchmark: 10 Symbols ---")
    print(json.dumps(res, indent=2))
    assert res["tick_count"] == 10000
    assert res["p50_us"] > 0
    assert res["ticks_per_second"] > 1000.0
