"""Unit tests for Metrics Service."""

from __future__ import annotations

import time
import pytest
from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.services.metrics_service import MetricsService


def test_metrics_service_collection():
    container = Container()
    bus = InMemoryEventBus()
    container.register("event_bus", instance=bus)

    # Fast sampling interval for testing
    service = MetricsService(collection_interval=0.1, max_history=10, container=container)
    service.start()

    time.sleep(0.3)

    service.stop()

    current = service.get_current()
    assert current != {}
    assert "cpu_percent" in current
    assert "memory_mb" in current
    assert "active_threads" in current

    history = service.get_history()
    assert len(history) >= 1

    summary = service.get_summary()
    assert summary["collection_count"] >= 1
    assert summary["avg_memory_mb"] > 0.0
