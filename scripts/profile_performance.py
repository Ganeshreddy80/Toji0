#!/usr/bin/env python3
"""TOJI Performance Profiler Script.

Measures latency profile metrics including boot time, event propagation,
execution queue latency, broker execution, and dashboard snapshot fetching.
"""

from __future__ import annotations

import argparse
import logging
import time
import tracemalloc
from datetime import datetime, timezone

from toji_platform.boot import boot_kernel
from toji_platform.core.event_bus.events import MarketDataReceived
from data.schemas.market_data import OHLCV

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def run_profiling() -> dict[str, float]:
    """Profile the system and return measured metrics."""
    tracemalloc.start()
    
    # 1. Profile boot time
    start_boot = time.perf_counter()
    kernel = boot_kernel(config_overrides={"market_gateway.provider_mode": "replay"})
    boot_time_ms = (time.perf_counter() - start_boot) * 1000.0

    # Connect paper broker
    from execution_engine.core.interfaces import IExecutionEngine
    exec_engine = kernel.container.resolve(IExecutionEngine)
    paper_broker = exec_engine._broker_router.get_adapter("paper")
    paper_broker.connect()

    # 2. Profile Event Loop Propagation latency
    bus = kernel.event_bus
    latencies = []

    def get_tracker():
        def tracker(event):
            latencies.append(time.perf_counter())
        return tracker

    # We track end-to-end pipeline latency from MarketDataReceived down to DashboardUpdated
    bus.subscribe("system.dashboard_updated", get_tracker())

    candle = OHLCV(
        symbol="BTC/USDT",
        interval="1m",
        open=50000.0,
        high=55000.0,
        low=45000.0,
        close=52000.0,
        volume=10.0,
        timestamp=datetime.now(timezone.utc),
    )
    market_event = MarketDataReceived(
        source="profiler",
        payload={"symbol": "BTC/USDT", "candle": candle.model_dump()},
    )

    start_event = time.perf_counter()
    bus.publish(market_event)

    # Calculate latency if the pipeline completed
    processing_latency_ms = 0.0
    if latencies:
        processing_latency_ms = (latencies[0] - start_event) * 1000.0

    # 3. Profile Execution Engine latency
    from execution_engine.core.models import ExecutionRequest
    from execution_engine.core.enums import OrderSide, OrderType, OrderTimeInForce

    req = ExecutionRequest(
        execution_id="prof-exec-1",
        request_id="prof-req-1",
        signal_id="prof-sig-1",
        strategy_id="prof-strat-1",
        position_id="prof-pos-1",
        correlation_id="prof-corr-1",
        symbol="BTC/USDT",
        timeframe="1m",
        quantity=20.0,
        price=50000.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        time_in_force=OrderTimeInForce.GTC,
        leverage=1.0,
        margin_required=10.0,
        timestamp=datetime.now(timezone.utc),
    )

    start_execution = time.perf_counter()
    result = exec_engine.submit_execution(req)
    execution_latency_ms = (time.perf_counter() - start_execution) * 1000.0

    # 4. Profile Dashboard endpoint query latency
    from dashboard.core.interfaces import IDashboardStateStore
    dashboard_store = kernel.container.resolve(IDashboardStateStore)

    start_dash = time.perf_counter()
    snapshot = dashboard_store.get_snapshot("BTC/USDT", "all")
    dashboard_query_latency_ms = (time.perf_counter() - start_dash) * 1000.0

    # Clean up kernel
    kernel.shutdown()
    
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("=" * 60)
    print(" PERFORMANCE BENCHMARK PROFILE")
    print("=" * 60)
    print(f" Platform Boot Time      : {boot_time_ms:.2f} ms")
    print(f" Event Pipeline Latency  : {processing_latency_ms:.2f} ms")
    print(f" Execution Submit Time   : {execution_latency_ms:.2f} ms")
    print(f" Dashboard Fetch Time    : {dashboard_query_latency_ms:.2f} ms")
    print(f" Peak Memory Traced      : {peak_mem / (1024 * 1024):.2f} MB")
    print("=" * 60)

    return {
        "boot_time_ms": boot_time_ms,
        "event_pipeline_latency_ms": processing_latency_ms,
        "execution_latency_ms": execution_latency_ms,
        "dashboard_query_latency_ms": dashboard_query_latency_ms,
        "peak_memory_mb": peak_mem / (1024 * 1024),
    }


if __name__ == "__main__":
    run_profiling()
