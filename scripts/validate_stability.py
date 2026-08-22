#!/usr/bin/env python3
"""TOJI Stability Validation Script.

Runs the TOJI platform continuously in replay mode for a configured duration,
monitoring memory usage, thread count, queue depths, and event timelines
to verify continuous paper trading robustness.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import threading
import tracemalloc
from datetime import datetime, timezone

from toji_platform.boot import boot_kernel
from toji_platform.core.event_bus.events import MarketDataReceived
from data.schemas.market_data import OHLCV

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("toji.stability")


def run_stability_check(duration_seconds: float) -> dict[str, any]:
    """Run continuous stream of mock market ticks and measure stability."""
    print("=" * 60)
    print(f" Starting TOJI Stability Validation (Duration: {duration_seconds}s)")
    print("=" * 60)

    tracemalloc.start()
    start_time = time.perf_counter()
    initial_memory = 0

    # Boot kernel
    logger.info("Booting TOJI platform kernel in replay mode...")
    kernel = boot_kernel(config_overrides={"market_gateway.provider_mode": "replay"})

    # Connect paper broker
    from execution_engine.core.interfaces import IExecutionEngine
    exec_engine = kernel.container.resolve(IExecutionEngine)
    paper_broker = exec_engine._broker_router.get_adapter("paper")
    paper_broker.connect()

    bus = kernel.event_bus

    # 1. Warm-up Phase: run 5 ticks to trigger lazy imports/loadings
    logger.info("Executing 5 warm-up ticks to load lazy components...")
    for w in range(5):
        candle = OHLCV(
            symbol="BTC/USDT",
            interval="1m",
            open=50000.0,
            high=50500.0,
            low=49900.0,
            close=50200.0,
            volume=1.5,
            timestamp=datetime.now(timezone.utc),
        )
        market_event = MarketDataReceived(
            source="stability_warmup",
            payload={"symbol": "BTC/USDT", "candle": candle.model_dump()},
        )
        try:
            bus.publish(market_event)
        except Exception:
            pass
        time.sleep(0.05)

    # Capture initial baseline memory after warm-up completes
    initial_memory = tracemalloc.get_traced_memory()[0]
    start_time = time.perf_counter()

    tick_count = 0
    errors = 0
    timeline_depths = []

    logger.info("Starting continuous event loop streaming ticks...")
    try:
        while time.perf_counter() - start_time < duration_seconds:
            tick_count += 1
            # Generate tick
            candle = OHLCV(
                symbol="BTC/USDT",
                interval="1m",
                open=50000.0 + tick_count,
                high=50500.0 + tick_count,
                low=49900.0 + tick_count,
                close=50200.0 + tick_count,
                volume=1.5,
                timestamp=datetime.now(timezone.utc),
            )
            market_event = MarketDataReceived(
                source="stability_validator",
                payload={"symbol": "BTC/USDT", "candle": candle.model_dump()},
            )

            try:
                bus.publish(market_event)
            except Exception as e:
                logger.error("Event dispatch error: %s", e)
                errors += 1

            # Sleep to simulate real tick speed/frequency
            time.sleep(0.1)

            if tick_count % 10 == 0:
                current_mem = tracemalloc.get_traced_memory()[0]
                active_threads = threading.active_count()
                timeline_len = len(bus.get_timeline())
                timeline_depths.append(timeline_len)
                logger.info(
                    "Status: ticks=%d | memory_mb=%.2f | active_threads=%d | timeline_size=%d",
                    tick_count,
                    current_mem / (1024 * 1024),
                    active_threads,
                    timeline_len,
                )

    except KeyboardInterrupt:
        logger.info("Continuous stability test interrupted by user.")
    finally:
        logger.info("Initiating platform kernel shutdown...")
        kernel.shutdown()

    end_time = time.perf_counter()
    final_mem = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    duration = end_time - start_time
    mem_leak = final_mem - initial_memory

    results = {
        "duration_seconds": duration,
        "ticks_processed": tick_count,
        "errors_encountered": errors,
        "memory_leak_bytes": mem_leak,
        "final_active_threads": threading.active_count(),
        "stable": errors == 0 and mem_leak < 100 * 1024 * 1024,  # Under 100MB increase
    }

    print("=" * 60)
    print(" STABILITY REPORT SUMMARY")
    print("=" * 60)
    print(f" Duration        : {duration:.2f}s")
    print(f" Ticks Processed : {tick_count}")
    print(f" Errors          : {errors}")
    print(f" Memory Delta    : {mem_leak / (1024 * 1024):.4f} MB")
    print(f" Active Threads  : {results['final_active_threads']}")
    print(f" Stable Result   : {results['stable']}")
    print("=" * 60)

    return results


def main() -> None:
    """CLI entry point for stability testing."""
    parser = argparse.ArgumentParser(description="TOJI Continuous Stability Validator")
    parser.add_argument("--duration", type=float, default=5.0, help="Test duration in seconds")
    args = parser.parse_args()

    results = run_stability_check(args.duration)
    if not results["stable"]:
        logger.error("Stability check failed! Resource leaks or exceptions detected.")
        sys.exit(1)
    logger.info("Stability validation passed successfully.")


if __name__ == "__main__":
    main()
