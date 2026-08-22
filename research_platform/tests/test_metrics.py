"""Comprehensive unit and integration tests for R55 Metrics & Observability Subsystem.
"""

from __future__ import annotations

import pytest
import time
import unittest.mock
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.platform.service_registry import ServiceRegistry

from research_platform.metrics.models import MetricPoint, MetricSeries, MetricType, MetricUnit, PlatformSnapshot
from research_platform.metrics.collectors import SystemMetricsCollector, TradingMetricsCollector
from research_platform.metrics.registry import MetricsRegistry
from research_platform.metrics.snapshot import SnapshotBuilder
from research_platform.metrics.orchestrator import MetricsOrchestrator
from research_platform.metrics.plugin import MetricsPlugin


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)
    return c


class TestMetricsModels:
    def test_metric_point_creation(self):
        point = MetricPoint(name="cpu_usage", value=45.5, metric_type=MetricType.GAUGE, unit=MetricUnit.PERCENT)
        assert point.metric_id is not None
        assert point.name == "cpu_usage"
        assert point.value == 45.5
        assert point.timestamp is not None

    def test_metric_series(self):
        point1 = MetricPoint(name="m", value=1.0)
        point2 = MetricPoint(name="m", value=2.0)
        series = MetricSeries(name="m", points=[point1, point2], unit=MetricUnit.COUNT)
        
        assert series.latest().value == 2.0
        assert series.values() == [1.0, 2.0]

    def test_platform_snapshot_defaults(self):
        snap = PlatformSnapshot()
        assert snap.snapshot_id is not None
        assert snap.cpu_pct == 0.0
        assert snap.certification_status == "UNKNOWN"
        assert snap.uptime_sec >= 0.0


class TestSystemMetricsCollector:
    def test_collect_all(self):
        collector = SystemMetricsCollector()
        
        cpu = collector.collect_cpu()
        assert cpu.name == "system.cpu_pct"
        assert cpu.metric_type == MetricType.GAUGE
        
        mem = collector.collect_memory()
        assert mem.name == "system.memory_mb"
        assert mem.unit == MetricUnit.MEGABYTES
        
        disk = collector.collect_disk()
        assert disk.name == "system.free_disk_gb"
        assert disk.value >= 0.0
        
        threads = collector.collect_threads()
        assert threads.name == "system.active_threads"
        assert threads.value > 0


class TestMetricsRegistry:
    def test_record_and_query(self):
        registry = MetricsRegistry()
        point1 = MetricPoint(name="test.metric", value=10.0)
        point2 = MetricPoint(name="test.metric", value=15.0)
        
        registry.record(point1)
        registry.record(point2)
        
        assert registry.total_count() == 2
        assert "test.metric" in registry.list_metrics()
        
        series = registry.get_series("test.metric", limit=5)
        assert len(series.points) == 2
        assert series.latest().value == 15.0
        
        latest = registry.get_latest("test.metric")
        assert latest.value == 15.0

    def test_record_value(self):
        registry = MetricsRegistry()
        point = registry.record_value("test.value", 100.0, unit=MetricUnit.DOLLARS)
        assert point.name == "test.value"
        assert point.value == 100.0
        assert point.unit == MetricUnit.DOLLARS
        assert registry.total_count() == 1

    def test_clear_registry(self):
        registry = MetricsRegistry()
        registry.record_value("a", 1.0)
        assert registry.total_count() == 1
        registry.clear()
        assert registry.total_count() == 0


class TestSnapshotBuilder:
    def test_build_snapshot(self):
        builder = SnapshotBuilder()
        snap = builder.build()
        assert isinstance(snap, PlatformSnapshot)
        assert snap.cpu_pct >= 0.0
        assert snap.active_threads > 0


class TestMetricsOrchestrator:
    def test_orchestrator_collect_once(self, container):
        # Register EventBus in ServiceRegistry for orchestrator integration
        event_bus = container.resolve("IEventBus")
        ServiceRegistry().register_service("EventBus", event_bus)

        orchestrator = MetricsOrchestrator(interval_sec=0.1)
        orchestrator.collect_once()
        
        # Verify metric registration
        registry = orchestrator.registry
        assert "system.cpu_pct" in registry.list_metrics()
        assert "system.memory_mb" in registry.list_metrics()
        assert "system.active_threads" in registry.list_metrics()
        
        # Verify snapshot builder output
        snap = orchestrator.get_snapshot()
        assert isinstance(snap, PlatformSnapshot)
        assert snap.active_threads > 0

    def test_orchestrator_loop_lifecycle(self, container):
        event_bus = container.resolve("IEventBus")
        ServiceRegistry().register_service("EventBus", event_bus)

        orchestrator = MetricsOrchestrator(interval_sec=0.01)
        orchestrator.start()
        time.sleep(0.05)
        orchestrator.stop()
        
        assert orchestrator.registry.total_count() > 0


class TestMetricsPlugin:
    def test_plugin_initialize(self, container):
        plugin = MetricsPlugin(container)
        plugin.initialize()
        
        orchestrator = container.resolve("MetricsOrchestrator")
        assert orchestrator is not None
        assert isinstance(orchestrator, MetricsOrchestrator)
        
        registry = container.resolve("MetricsRegistry")
        assert registry is not None
        assert isinstance(registry, MetricsRegistry)
        
        assert plugin.health_check() == "HEALTHY"
        plugin.shutdown()
