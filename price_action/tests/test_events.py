"""Unit tests for Price Action Engine events."""

from __future__ import annotations

from price_action.core.events import (
    PriceActionInitialized,
    PriceActionShutdown,
    PatternDetected,
    PatternUpdated,
    PatternConfirmed,
    PatternInvalidated,
    PatternCompleted,
)
from toji_platform.core.event_bus import InMemoryEventBus


def test_event_routing_keys():
    """Verify that routing keys are derived correctly from classes."""
    init = PriceActionInitialized(source="test")
    assert init.event_type == "system.price_action_initialized"

    shutdown = PriceActionShutdown(source="test")
    assert shutdown.event_type == "system.price_action_shutdown"

    detected = PatternDetected(source="test", payload={"symbol": "BTCUSDT", "timeframe": "1h", "candidate": {}})
    assert detected.event_type == "system.pattern_detected"
    assert detected.payload["symbol"] == "BTCUSDT"

    updated = PatternUpdated(source="test", payload={"symbol": "BTCUSDT", "timeframe": "1h", "pattern_id": "1", "status": "DEVELOPING", "pattern": {}})
    assert updated.event_type == "system.pattern_updated"

    confirmed = PatternConfirmed(source="test", payload={"symbol": "BTCUSDT", "timeframe": "1h", "match": {}})
    assert confirmed.event_type == "system.pattern_confirmed"

    invalidated = PatternInvalidated(source="test", payload={"symbol": "BTCUSDT", "timeframe": "1h", "match": {}})
    assert invalidated.event_type == "system.pattern_invalidated"

    completed = PatternCompleted(source="test", payload={"symbol": "BTCUSDT", "timeframe": "1h", "match": {}})
    assert completed.event_type == "system.pattern_completed"


def test_event_bus_publishing():
    """Verify that Price Action events propagate correctly through the EventBus."""
    bus = InMemoryEventBus()
    received = []

    bus.subscribe("system.price_action_initialized", received.append)
    bus.subscribe("system.pattern_detected", received.append)

    init_event = PriceActionInitialized(source="plugin_test", payload={"version": "1.0.0"})
    bus.publish(init_event)

    detected_event = PatternDetected(
        source="orchestrator_test",
        payload={"symbol": "BTCUSDT", "timeframe": "1h", "candidate": {}},
    )
    bus.publish(detected_event)

    assert len(received) == 2
    assert received[0] == init_event
    assert received[1] == detected_event
