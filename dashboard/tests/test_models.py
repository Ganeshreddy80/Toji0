import pytest
from datetime import datetime, timezone
from dashboard.core.enums import HealthStatus
from dashboard.core.models import SubsystemHealth, DashboardSnapshot, HistoricalEvent


def test_subsystem_health_model() -> None:
    """Test SubsystemHealth initialization and constraints."""
    now = datetime.now(timezone.utc)
    health = SubsystemHealth(
        status=HealthStatus.HEALTHY,
        last_update=now,
        processing_latency_ms=12.5,
        message_count=100,
        replay_status="LIVE",
    )
    assert health.status == HealthStatus.HEALTHY
    assert health.last_update == now
    assert health.processing_latency_ms == 12.5
    assert health.message_count == 100
    assert health.replay_status == "LIVE"


def test_dashboard_snapshot_model() -> None:
    """Test DashboardSnapshot initialization, default factory, and serialization."""
    now = datetime.now(timezone.utc)
    health = SubsystemHealth(
        status=HealthStatus.HEALTHY,
        last_update=now,
        processing_latency_ms=12.5,
        message_count=100,
        replay_status="LIVE",
    )
    snapshot = DashboardSnapshot(
        snapshot_id="test-uuid",
        symbol="BTC/USD",
        timeframe="1h",
        market_state={"trend": "BULLISH"},
        health_status={"MIL": health},
    )
    assert snapshot.snapshot_id == "test-uuid"
    assert snapshot.symbol == "BTC/USD"
    assert snapshot.timeframe == "1h"
    assert snapshot.market_state == {"trend": "BULLISH"}
    assert snapshot.health_status["MIL"].status == HealthStatus.HEALTHY
    assert snapshot.version == "1.0.0"


def test_historical_event_model() -> None:
    """Test HistoricalEvent fields validation."""
    now = datetime.now(timezone.utc)
    event = HistoricalEvent(
        event_id="evt-uuid",
        timestamp=now,
        subsystem="MIL",
        event_name="MarketStateUpdated",
        symbol="BTC/USD",
        timeframe="1h",
        latency_ms=10.2,
        severity="INFO",
        payload={"data": 123},
    )
    assert event.event_id == "evt-uuid"
    assert event.timestamp == now
    assert event.subsystem == "MIL"
    assert event.event_name == "MarketStateUpdated"
    assert event.symbol == "BTC/USD"
    assert event.timeframe == "1h"
    assert event.latency_ms == 10.2
    assert event.severity == "INFO"
    assert event.payload == {"data": 123}
