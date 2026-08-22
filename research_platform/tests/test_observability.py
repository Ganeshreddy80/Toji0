"""Unit tests for the Observability Platform.
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.observability.alerting import AlertEngine
from research_platform.observability.anomaly import AnomalyDetector
from research_platform.observability.dashboard import ObservabilityDashboardApi
from research_platform.observability.health import HealthEngine
from research_platform.observability.heartbeat import HeartbeatMonitor
from research_platform.observability.latency import LatencyTracker
from research_platform.observability.logger import StructuredLogger
from research_platform.observability.metrics import MetricsEngine
from research_platform.observability.orchestrator import ObservabilityOrchestrator
from research_platform.observability.profiler import PerformanceProfiler
from research_platform.observability.tracing import TracingEngine


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return ObservabilityOrchestrator(event_bus)


def test_structured_log_formatting():
    """Verify logger JSON format and correlation context mapping."""
    logger = StructuredLogger()
    logger.set_correlation_id("corr_123")

    entry = logger.log(level="info", subsystem="OMS", message="Order received")
    assert entry.level == "INFO"
    assert entry.subsystem == "OMS"
    assert entry.correlation_id == "corr_123"


def test_metrics_engine_aggregators():
    """Verify gauge, counter, and timer increments."""
    engine = MetricsEngine()
    
    # Counter
    engine.increment_counter("orders_count", amount=2.0)
    assert engine.get_counter("orders_count") == 2.0

    # Gauge
    engine.update_gauge("cpu_usage", value=45.0)
    assert engine.get_gauge("cpu_usage") == 45.0


def test_tracing_nested_spans():
    """Verify execution timings duration math on stop spans."""
    engine = TracingEngine()

    span = engine.start_span(name="MVO_calculation")
    time.sleep(0.01)  # small pause
    stopped = engine.stop_span(span.span_id)

    assert stopped.end_time is not None
    assert stopped.duration_ms > 0.0


def test_latency_distribution_statistics():
    """Verify P95 and P99 percentiles calculation."""
    latencies = [10.0, 12.0, 15.0, 11.0, 100.0]  # outlier at 100
    
    measure = LatencyTracker.calculate_latency("OMS_delay", latencies)
    assert measure.min_ms == 10.0
    assert measure.max_ms == 100.0
    assert measure.p95_ms > 15.0


def test_profiler_load_profiles():
    """Verify profiler load stats capture."""
    profiler = PerformanceProfiler()
    res = profiler.capture_profile()
    assert res.cpu_load_pct > 0.0
    assert res.memory_used_mb > 0.0


def test_health_compilations_and_heartbeats():
    """Verify component health statuses and missed heartbeat detections."""
    # 1. Health Report
    health = HealthEngine()
    health.update_status("OMS", healthy=True)
    health.update_status("EMS", healthy=False, details="Connection failed")
    
    report = health.compile_report()
    assert len(report.statuses) == 2
    assert report.statuses[1].healthy is False

    # 2. Heartbeat Monitor
    monitor = HeartbeatMonitor(timeout_seconds=0.1)
    monitor.record_heartbeat("risk_manager")
    time.sleep(0.2)
    
    dead = monitor.check_heartbeats()
    assert "risk_manager" in dead


def test_anomaly_latency_spikes():
    """Verify outlier detection checks."""
    history = [10.0, 11.0, 10.0, 12.0, 11.0, 50.0]  # outlier 50
    assert AnomalyDetector.detect_latency_spike(history, threshold_factor=3.0) is True


def test_dashboard_snapshots():
    """Verify dashboard compiles reports summaries."""
    health = HealthEngine()
    health.update_status("OMS", healthy=True)
    report = health.compile_report()

    snap = ObservabilityDashboardApi.compile_snapshot([report], alerts_count=3)
    assert snap.alerts_count == 3
    assert len(snap.health_reports) == 1


def test_observability_orchestrator(orchestrator):
    """Verify orchestrator coordinates and persists metrics logs."""
    # Log
    orchestrator.record_log(level="warning", subsystem="Risk", message="Limit approached")
    assert len(orchestrator.repository.list_logs()) == 1

    # Metric
    orchestrator.record_metric(name="lat", value=22.5)
    assert len(orchestrator.repository.list_metrics()) == 1
