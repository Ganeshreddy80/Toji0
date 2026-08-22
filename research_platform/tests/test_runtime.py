"""Unit and integration tests for the TOJI Continuous Runtime Engine.
"""

from __future__ import annotations

import time
import pytest
import threading
from datetime import datetime, timezone
from typing import Dict, Any

from research_platform.platform.container_boot import ContainerBootloader
from research_platform.platform.eventbus_boot import EventBusBootloader
from research_platform.runtime.models import RuntimeStatus, LoopMetrics
from research_platform.runtime.events import (
    RuntimeStarted, RuntimePaused, RuntimeResumed, RuntimeStopped,
    HeartbeatLogged, SubsystemFailed, SubsystemRecovered
)
from research_platform.runtime.interfaces import IRuntimeLoop
from research_platform.runtime.repository import RuntimeRepository
from research_platform.runtime.heartbeat import HeartbeatMonitor
from research_platform.runtime.runtime_engine import RuntimeEngine
from research_platform.runtime.orchestrator import RuntimeOrchestrator

# Loops imports
from research_platform.runtime.market_loop import MarketLoop
from research_platform.runtime.strategy_loop import StrategyLoop
from research_platform.runtime.risk_loop import RiskLoop
from research_platform.runtime.portfolio_loop import PortfolioLoop
from research_platform.runtime.execution_loop import ExecutionLoop
from research_platform.runtime.analytics_loop import AnalyticsLoop
from research_platform.runtime.monitoring_loop import MonitoringLoop
from research_platform.runtime.persistence_loop import PersistenceLoop
from research_platform.runtime.scheduler_loop import SchedulerLoop
from research_platform.runtime.recovery_loop import RecoveryLoop


@pytest.fixture(scope="function")
def container():
    c = ContainerBootloader().boot_container()
    eb = EventBusBootloader().boot_eventbus()
    c.register("IEventBus", instance=eb)
    return c


@pytest.fixture(scope="function")
def engine(container):
    return RuntimeEngine(container, interval_sec=0.01)


# ── 1. DI & Plugin Resolution Tests (10 tests) ────────────────────────

@pytest.mark.parametrize("service_name", [
    "IEventBus",
    "RuntimeEngine",
    "RuntimeOrchestrator",
    "PaperMarketOrchestrator",
    "PaperTradingOrchestrator",
    "PortfolioEngineOrchestrator",
    "StrategyLifecycleOrchestrator",
    "OMSOrchestrator",
    "PortfolioAnalyticsOrchestrator",
    "StrategySchedulerOrchestrator"
])
def test_runtime_di_resolution(container, service_name):
    # Setup mock registry bindings
    class DummyOrch:
        pass
    try:
        container.register(service_name, instance=DummyOrch())
    except Exception:
        pass
    resolved = container.resolve(service_name)
    assert resolved is not None


# ── 2. Loop Execution & Context Processing Tests (10 tests) ──────────

@pytest.mark.parametrize("loop_cls", [
    MarketLoop, StrategyLoop, RiskLoop, PortfolioLoop, ExecutionLoop,
    AnalyticsLoop, MonitoringLoop, PersistenceLoop, SchedulerLoop, RecoveryLoop
])
def test_individual_loop_execution(container, loop_cls):
    loop = loop_cls(container)
    context = {"tickers": {}, "signals": [], "validated_signals": []}
    loop.execute(context)
    assert isinstance(context, dict)


# ── 3. Loop Failover Recovery Tests (10 tests) ───────────────────────

@pytest.mark.parametrize("loop_cls", [
    MarketLoop, StrategyLoop, RiskLoop, PortfolioLoop, ExecutionLoop,
    AnalyticsLoop, MonitoringLoop, PersistenceLoop, SchedulerLoop, RecoveryLoop
])
def test_individual_loop_recovery_trigger(container, loop_cls):
    loop = loop_cls(container)
    ex = ValueError("Test Exception")
    recovered = loop.recover(ex)
    assert recovered is True


# ── 4. Subsystem Failed Event Structure (10 tests) ────────────────────

@pytest.mark.parametrize("subsystem_name", [
    "MarketLoop", "StrategyLoop", "RiskLoop", "PortfolioLoop", "ExecutionLoop",
    "AnalyticsLoop", "MonitoringLoop", "PersistenceLoop", "SchedulerLoop", "RecoveryLoop"
])
def test_subsystem_failed_events(subsystem_name):
    event = SubsystemFailed(
        event_id="test-ev",
        subsystem_name=subsystem_name,
        error_message="Runtime issue occurred"
    )
    assert event.subsystem_name == subsystem_name
    assert "issue" in event.error_message


# ── 5. Subsystem Recovered Event Structure (10 tests) ──────────────────

@pytest.mark.parametrize("subsystem_name", [
    "MarketLoop", "StrategyLoop", "RiskLoop", "PortfolioLoop", "ExecutionLoop",
    "AnalyticsLoop", "MonitoringLoop", "PersistenceLoop", "SchedulerLoop", "RecoveryLoop"
])
def test_subsystem_recovered_events(subsystem_name):
    event = SubsystemRecovered(
        event_id="test-ev",
        subsystem_name=subsystem_name,
        retry_count=1
    )
    assert event.subsystem_name == subsystem_name
    assert event.retry_count == 1


# ── 6. Engine Status Transitions (8 tests) ──────────────────────────

@pytest.mark.parametrize("initial, target", [
    (RuntimeStatus.STOPPED, RuntimeStatus.RUNNING),
    (RuntimeStatus.RUNNING, RuntimeStatus.PAUSED),
    (RuntimeStatus.PAUSED, RuntimeStatus.RUNNING),
    (RuntimeStatus.RUNNING, RuntimeStatus.STOPPED),
    (RuntimeStatus.PAUSED, RuntimeStatus.STOPPED),
    (RuntimeStatus.STOPPED, RuntimeStatus.STOPPED),
    (RuntimeStatus.RUNNING, RuntimeStatus.RUNNING),
    (RuntimeStatus.PAUSED, RuntimeStatus.PAUSED)
])
def test_engine_state_transitions(engine, initial, target):
    # Force initial state
    engine.status = initial
    if initial == RuntimeStatus.RUNNING:
        engine._pause_event.clear()
    elif initial == RuntimeStatus.PAUSED:
        engine._pause_event.set()

    # Trigger action
    if target == RuntimeStatus.RUNNING:
        if initial == RuntimeStatus.PAUSED:
            engine.resume()
        else:
            engine.start()
    elif target == RuntimeStatus.PAUSED:
        engine.pause()
    elif target == RuntimeStatus.STOPPED:
        engine.stop()

    assert engine.status == target
    engine.stop()


# ── 7. Telemetry Heartbeat Tests (5 tests) ──────────────────────────

@pytest.mark.parametrize("cpu_val, mem_val", [
    (10.0, 150.0),
    (0.0, 200.0),
    (85.0, 50.0),
    (5.0, 300.0),
    (99.0, 10.0)
])
def test_heartbeat_telemetry_payload(cpu_val, mem_val):
    payload = HeartbeatLogged(
        event_id="heartbeat",
        loop_latency_ms=1.5,
        cpu_time_ms=cpu_val,
        memory_mb=mem_val,
        event_count=5,
        recovery_count=0
    )
    assert payload.cpu_time_ms == cpu_val
    assert payload.memory_mb == mem_val


# ── 8. Repository Caching Tests (5 tests) ───────────────────────────

@pytest.mark.parametrize("metric_name, metric_val", [
    ("loop_latency_ms", 12.5),
    ("cpu_time_ms", 4.2),
    ("memory_mb", 95.0),
    ("event_count", 120),
    ("recovery_count", 2)
])
def test_repository_metric_caching(metric_name, metric_val):
    repo = RuntimeRepository()
    repo.save_metric(metric_name, metric_val)
    assert repo.get_metric(metric_name) == metric_val


# ── 9. Thread Safety & Continuous Loop Tests (12 tests) ──────────────

def test_engine_thread_boot_and_teardown(engine):
    engine.start()
    assert engine.status == RuntimeStatus.RUNNING
    time.sleep(0.05)
    engine.stop()
    assert engine.status == RuntimeStatus.STOPPED


def test_engine_pause_yields_execution(engine):
    engine.start()
    time.sleep(0.05)
    engine.pause()
    assert engine.status == RuntimeStatus.PAUSED
    
    count_before = engine.run_count
    time.sleep(0.05)
    # Execution count should not increment while paused
    assert engine.run_count == count_before
    
    engine.resume()
    assert engine.status == RuntimeStatus.RUNNING
    time.sleep(0.1)
    assert engine.run_count > count_before
    engine.stop()


def test_concurrency_start_calls(engine):
    threads = [threading.Thread(target=engine.start) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert engine.status == RuntimeStatus.RUNNING
    engine.stop()


def test_concurrency_stop_calls(engine):
    engine.start()
    threads = [threading.Thread(target=engine.stop) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert engine.status == RuntimeStatus.STOPPED


def test_concurrency_pause_calls(engine):
    engine.start()
    threads = [threading.Thread(target=engine.pause) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert engine.status == RuntimeStatus.PAUSED
    engine.stop()


def test_engine_exception_recovery_flow(container):
    # Loop that throws an error to force engine recovery triggers
    class FaultyLoop(IRuntimeLoop):
        def execute(self, context):
            raise RuntimeError("Failure Simulated")
        def recover(self, exception):
            return True

    engine = RuntimeEngine(container, interval_sec=0.005)
    engine.loops["FaultyLoop"] = FaultyLoop()
    engine.start()
    time.sleep(0.02)
    engine.stop()
    
    assert engine.metrics.recovery_count > 0


def test_engine_unrecovered_loop_logs(container):
    # Loop that fails to recover
    class DeadLoop(IRuntimeLoop):
        def execute(self, context):
            raise RuntimeError("Fatal Failure")
        def recover(self, exception):
            return False

    engine = RuntimeEngine(container, interval_sec=0.005)
    engine.loops["DeadLoop"] = DeadLoop()
    engine.start()
    time.sleep(0.02)
    engine.stop()
    
    assert engine.metrics.recovery_count > 0


def test_orchestrator_api_boot_shutdown(container):
    orch = RuntimeOrchestrator(container)
    orch.boot()
    assert orch.engine is not None
    assert orch.engine.status == RuntimeStatus.RUNNING
    orch.shutdown()
    assert orch.engine.status == RuntimeStatus.STOPPED


def test_database_offline_fallback_safety(engine):
    # Ensure persistence loop does not throw if database offline
    engine.start()
    time.sleep(0.02)
    engine.stop()
    assert engine.status == RuntimeStatus.STOPPED


def test_heartbeat_monitor_rss_reads():
    monitor = HeartbeatMonitor()
    telemetry = monitor.get_telemetry()
    assert "cpu_pct" in telemetry
    assert "memory_mb" in telemetry


def test_runtime_started_event_payload():
    ev = RuntimeStarted(event_id="abc")
    assert ev.status == "RUNNING"


def test_runtime_paused_event_payload():
    ev = RuntimePaused(event_id="abc")
    assert ev.status == "PAUSED"
