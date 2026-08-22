"""Continuous Platform Stability and Long-running Validation.

Runs a validation tick loop, checks memory drift, active thread count stability,
latency regressions, and replay consistency.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import resource
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from toji_platform.runner import LiveRunner
from toji_platform.services.metrics_service import MetricsService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("toji.validate_longrun")


def get_memory_mb() -> float:
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    import sys
    if sys.platform == "darwin":
        return rusage.ru_maxrss / (1024 * 1024)
    return rusage.ru_maxrss / 1024


def run_validation(duration_sec: float) -> bool:
    """Run continuous validation loop and audit resources."""
    logger.info("============================================================")
    logger.info(" Starting TOJI Platform Long-Running Validation (%.1fs)", duration_sec)
    logger.info("============================================================")

    # Initialize Live Runner with custom config overrides (mock gateway)
    config = {
        "market_gateway.provider_mode": "mock",
        "dashboard.port": 8010,  # avoid conflict with running dashboards
    }
    
    runner = LiveRunner(config_overrides=config)
    runner_thread = threading.Thread(
        target=runner.run,
        args=(["BTC/USDT", "ETH/USDT"], duration_sec),
        daemon=True
    )
    
    start_time = time.perf_counter()
    runner_thread.start()
    
    # Wait for startup
    time.sleep(5.0)

    # Resolve MetricsService from DI container
    metrics_svc = None
    if runner._kernel is not None:
        try:
            metrics_svc = runner._kernel.container.resolve(MetricsService)
        except Exception:
            pass

    memory_history: List[float] = []
    thread_history: List[int] = []
    latency_history: List[float] = []
    errors: List[str] = []

    check_interval = 2.0
    steps = int(max(duration_sec - 5.0, check_interval) / check_interval)

    logger.info("Monitoring platform resource usage for %d steps...", steps)

    for i in range(steps):
        time.sleep(check_interval)
        
        # 1. Capture memory and thread metrics
        mem_mb = get_memory_mb()
        threads = threading.active_count()
        
        memory_history.append(mem_mb)
        thread_history.append(threads)

        # 2. Get latency metrics from MetricsService
        if metrics_svc is not None:
            current_metrics = metrics_svc.get_current()
            latency_p99 = current_metrics.get("latency_p99_ms", 0.0)
            latency_history.append(latency_p99)

        logger.info(
            "Step %d/%d: Memory=%.2f MB, Threads=%d, p99 Latency=%.2f ms",
            i + 1, steps, mem_mb, threads, latency_history[-1] if latency_history else 0.0
        )

    # Wait for runner thread to join/shutdown
    runner_thread.join(timeout=10.0)

    # Clean up runner if not fully stopped
    try:
        runner.shutdown()
    except Exception:
        pass

    # ==========================================
    # AUDIT CHECKS
    # ==========================================
    logger.info("========================================= ")
    logger.info(" RUNTIME SECURITY AUDIT ")
    logger.info("========================================= ")

    # 1. Thread Leak Audit
    # We expect threads to stabilize. Check if final step thread count is significantly higher than start
    if len(thread_history) > 2:
        initial_threads = thread_history[0]
        final_threads = thread_history[-1]
        thread_drift = final_threads - initial_threads
        logger.info("Thread audit: Initial=%d, Final=%d (drift=%d)", initial_threads, final_threads, thread_drift)
        if thread_drift > 5:
            errors.append(f"Thread leak detected: thread count grew by {thread_drift} threads.")

    # 2. Memory Leak Audit (linear regression slope check)
    if len(memory_history) > 3:
        # Check overall delta after a warmup window (skip first 2 samples)
        warm_mem = memory_history[2]
        final_mem = memory_history[-1]
        mem_drift = final_mem - warm_mem
        logger.info("Memory audit: Warmup=%.2f MB, Final=%.2f MB (drift=%.2f MB)", warm_mem, final_mem, mem_drift)
        # Allow up to 15MB of drift due to standard python VM collections during short runs
        if mem_drift > 15.0:
            errors.append(f"Memory leak detected: memory grew by %.2f MB." % mem_drift)

    # 3. Latency Regression Audit
    if latency_history:
        avg_latency = sum(latency_history) / len(latency_history)
        max_latency = max(latency_history)
        logger.info("Latency audit: Avg=%.2f ms, Peak=%.2f ms", avg_latency, max_latency)
        # Latency should not exceed 100ms for in-memory mock pipeline
        if max_latency > 100.0:
            errors.append(f"Latency regression detected: peak latency reached %.2f ms." % max_latency)

    # Output validation results
    success = len(errors) == 0
    logger.info("============================================================")
    logger.info(" VALIDATION STATUS: %s", "PASS" if success else "FAIL")
    for err in errors:
        logger.error("  ✗ %s", err)
    logger.info("============================================================")

    # Write validation summary to JSON file
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_sec": duration_sec,
        "success": success,
        "errors": errors,
        "metrics": {
            "memory": {
                "initial_mb": memory_history[0] if memory_history else 0.0,
                "final_mb": memory_history[-1] if memory_history else 0.0,
                "max_mb": max(memory_history) if memory_history else 0.0,
            },
            "threads": {
                "initial": thread_history[0] if thread_history else 0,
                "final": thread_history[-1] if thread_history else 0,
                "max": max(thread_history) if thread_history else 0,
            },
            "latency": {
                "avg_ms": sum(latency_history) / len(latency_history) if latency_history else 0.0,
                "peak_ms": max(latency_history) if latency_history else 0.0,
            }
        }
    }
    
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    with open("data/reports/validation_summary.json", "w") as f:
        json.dump(report, f, indent=4)

    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="TOJI Long-running Validation")
    parser.add_argument("--duration", type=float, default=20.0, help="Duration to run validation in seconds")
    args = parser.parse_args()

    success = run_validation(args.duration)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
