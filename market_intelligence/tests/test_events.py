"""Unit tests for Market Intelligence Layer events."""

from __future__ import annotations

from market_intelligence.core.events import (
    ConfidenceUpdated,
    ContextUpdated,
    MILInitialized,
    MILShutdown,
    MarketSnapshotCreated,
    MarketStateUpdated,
    StoryGenerated,
)
from toji_platform.core.event_bus import InMemoryEventBus


def test_events_routing_keys():
    """Verify that routing keys are derived correctly from classes."""
    init = MILInitialized(source="test")
    assert init.event_type == "system.m_i_l_initialized"

    shutdown = MILShutdown(source="test")
    assert shutdown.event_type == "system.m_i_l_shutdown"

    state_upd = MarketStateUpdated(source="test", payload={"symbol": "BTCUSDT"})
    assert state_upd.event_type == "system.market_state_updated"
    assert state_upd.payload["symbol"] == "BTCUSDT"

    snap_created = MarketSnapshotCreated(source="test")
    assert snap_created.event_type == "system.market_snapshot_created"

    ctx_upd = ContextUpdated(source="test")
    assert ctx_upd.event_type == "system.context_updated"

    conf_upd = ConfidenceUpdated(source="test")
    assert conf_upd.event_type == "system.confidence_updated"

    story_gen = StoryGenerated(source="test")
    assert story_gen.event_type == "system.story_generated"


def test_event_bus_publishing():
    """Verify that MIL events can propagate through InMemoryEventBus."""
    bus = InMemoryEventBus()
    received = []

    bus.subscribe("system.m_i_l_initialized", received.append)
    bus.subscribe("system.market_state_updated", received.append)

    init_event = MILInitialized(source="test_source", payload={"version": "1.0.0"})
    bus.publish(init_event)

    state_event = MarketStateUpdated(
        source="test_source",
        payload={"symbol": "BTCUSDT", "timeframe": "1h", "state": {}},
    )
    bus.publish(state_event)

    assert len(received) == 2
    assert received[0] == init_event
    assert received[1] == state_event
