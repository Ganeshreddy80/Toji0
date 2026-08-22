"""Accelerated time simulation runner profiling resource usage, leakages, and recovery rollbacks."""

from __future__ import annotations

import os
import time
import json
import logging
import threading
import psutil
from datetime import datetime, timezone

from research_platform.bootstrap import bootstrap_platform, shutdown_platform, get_service
from research_platform.validation.models import ValidationDuration
from research_platform.platform.service_registry import ServiceRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_stats() -> dict:
    stats = {}
    try:
        db = ServiceRegistry().get_service("Database")
        if db:
            session = db.get_session()
            for table in ["orders", "trades", "positions", "configurations", "jobs", "monitoring_alerts", "reports"]:
                try:
                    res = session.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = res.scalar()
                except Exception:
                    stats[table] = 0
            session.close()
    except Exception as e:
        logger.error("Failed to query DB stats: %s", e)
    return stats


def run_accelerated_ticks(ticks: int) -> dict:
    proc = psutil.Process()
    start_time = time.perf_counter()
    start_cpu = time.process_time()
    start_mem = proc.memory_info().rss / (1024 * 1024)

    val_orch = get_service("ValidationOrchestrator")
    metrics_orch = get_service("MetricsOrchestrator")
    alert_orch = get_service("AlertOrchestrator")
    sched_orch = get_service("StrategySchedulerOrchestrator")

    # Disable periodic background daemon execution in tests to prevent overlap/interference
    if metrics_orch:
        metrics_orch.stop()
    if sched_orch:
        sched_orch.stop()

    cycle_durations = []
    events_published = 0

    for i in range(ticks):
        tick_start = time.perf_counter()
        
        # 1. Telemetry Capture
        if metrics_orch:
            metrics_orch.collect_once()

        # 2. Alert Evaluation
        if alert_orch:
            context = {
                "cpu_pct": 12.5,
                "free_disk_gb": 45.2,
                "drawdown_pct": 0.01 + (i % 100) * 0.0005,
                "certified": True
            }
            alert_orch.evaluate_context(context)

        # 3. Validation Checker runs
        if val_orch:
            val_orch.run_all(duration=ValidationDuration.QUICK)

        # 4. Scheduled Jobs
        if sched_orch:
            sched_orch._run_due_jobs()

        cycle_durations.append((time.perf_counter() - tick_start) * 1000)
        events_published += 4  # Estimate event emissions per tick

    end_time = time.perf_counter()
    end_cpu = time.process_time()
    end_mem = proc.memory_info().rss / (1024 * 1024)

    elapsed_wall = end_time - start_time
    elapsed_cpu = end_cpu - start_cpu

    avg_cycle_ms = sum(cycle_durations) / len(cycle_durations) if cycle_durations else 0.0
    throughput = events_published / elapsed_wall if elapsed_wall > 0 else 0.0

    return {
        "ticks_run": ticks,
        "elapsed_wall_sec": elapsed_wall,
        "elapsed_cpu_sec": elapsed_cpu,
        "mem_growth_mb": end_mem - start_mem,
        "peak_mem_mb": end_mem,
        "avg_cycle_ms": avg_cycle_ms,
        "event_throughput_per_sec": throughput,
        "active_threads": threading.active_count()
    }


def run_recovery_simulation() -> dict:
    """Simulates a checkpoint, crash scenario, and recovery boot sequence."""
    start_time = time.perf_counter()

    try:
        from research_platform.recovery.orchestrator import RecoveryOrchestrator
        from research_platform.platform.service_registry import ServiceRegistry
        
        event_bus = ServiceRegistry().get_service("EventBus")
        container = ServiceRegistry().get_service("Container")
        
        recovery_orch = RecoveryOrchestrator(container)

        # 1. Save checkpoint
        checkpoint = recovery_orch.trigger_checkpoint()
        assert checkpoint.checkpoint_id is not None
        checksum_before = checkpoint.integrity_hash

        # 2. Corrupt/Modify platform states (Simulate Crash)
        # e.g., register a degraded or missing service, or write invalid configurations
        db = ServiceRegistry().get_service("Database")
        if db:
            from sqlalchemy import text
            session = db.get_session()
            session.execute(text("INSERT INTO configurations (key, value) VALUES ('test_corruption_key', '\"corrupted\"')"))
            session.commit()
            session.close()

        # 3. Trigger recovery rollback
        rollback_success = recovery_orch.boot()
        
        # 4. Verify checkpoint checksum integrity matching
        restored_checkpoint = recovery_orch.repository.get_latest_checkpoint()
        checksum_after = restored_checkpoint.integrity_hash if restored_checkpoint else None
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "success": rollback_success,
            "duration_ms": duration_ms,
            "checksum_match": checksum_before == checksum_after,
            "checkpoint_id": checkpoint.checkpoint_id
        }
    except Exception as e:
        logger.error("Recovery simulation failed: %s", e)
        return {
            "success": False,
            "duration_ms": (time.perf_counter() - start_time) * 1000,
            "error": str(e)
        }


def run_full_simulation():
    logger.info("Initializing TOJI V1 Platform Simulation runner...")
    app = bootstrap_platform()

    try:
        logger.info("Running 24-Hour simulation block (288 ticks)...")
        stats_24h = run_accelerated_ticks(288)

        logger.info("Running 72-Hour simulation block (864 ticks)...")
        stats_72h = run_accelerated_ticks(864)

        logger.info("Running 7-Day simulation block (2016 ticks)...")
        stats_7d = run_accelerated_ticks(2016)

        logger.info("Running 30-Day simulation block (8640 ticks)...")
        stats_30d = run_accelerated_ticks(8640)

        logger.info("Running Crash & Rollback Recovery simulation...")
        recovery_stats = run_recovery_simulation()

        db_stats = get_db_stats()

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulation_24h": stats_24h,
            "simulation_72h": stats_72h,
            "simulation_7d": stats_7d,
            "simulation_30d": stats_30d,
            "recovery_metrics": recovery_stats,
            "database_rows": db_stats
        }

        output_path = "/Users/a.ganeshkumarreddy12/TOJI/research_platform/scratch/simulation_metrics.json"
        with open(output_path, "w", encoding="utf-8") as out:
            json.dump(report, out, indent=2)

        logger.info("Simulation run completed. Results written to %s", output_path)
        print(f"Peak RSS Memory usage: {stats_30d['peak_mem_mb']:.2f} MB")
        print(f"Memory growth over 30d simulation: {stats_30d['mem_growth_mb']:.4f} MB")
        print(f"Average loop tick latency: {stats_30d['avg_cycle_ms']:.4f} ms")
        print(f"Recovery Rollback execution time: {recovery_stats['duration_ms']:.2f} ms")
        print(f"Checksum integrity match: {recovery_stats.get('checksum_match', False)}")

    finally:
        shutdown_platform()


if __name__ == "__main__":
    run_full_simulation()
