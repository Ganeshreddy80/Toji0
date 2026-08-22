"""Tests for the Event Bus module."""

from __future__ import annotations

import pytest

from toji_platform.core.errors import EventBusError
from toji_platform.core.event_bus import (
    AssetSelected,
    BacktestCompleted,
    BaseEvent,
    DecisionGenerated,
    InMemoryEventBus,
    LearningCompleted,
    MarketDataUpdated,
    MemoryUpdated,
    ResearchCompleted,
    RiskCalculated,
    StrategyCreated,
    TradeRecorded,
)
from toji_platform.core.event_bus.interfaces import IEventHandler


class TestBaseEvent:
    """Tests for the BaseEvent frozen dataclass."""

    def test_auto_generates_event_id(self):
        e = BaseEvent(source="test")
        assert e.event_id is not None
        assert len(e.event_id) == 36  # UUID4

    def test_auto_generates_timestamp(self):
        e = BaseEvent(source="test")
        assert e.timestamp is not None

    def test_is_immutable(self):
        e = BaseEvent(source="test")
        with pytest.raises(AttributeError):
            e.source = "changed"  # type: ignore[misc]

    def test_event_type_derived_from_class_name(self):
        e = AssetSelected(source="test")
        assert e.event_type == "system.asset_selected"

    def test_payload_defaults_to_empty_dict(self):
        e = BaseEvent(source="test")
        assert e.payload == {}

    def test_payload_is_preserved(self):
        e = BaseEvent(source="test", payload={"key": "value"})
        assert e.payload == {"key": "value"}

    def test_two_events_have_different_ids(self):
        e1 = BaseEvent(source="a")
        e2 = BaseEvent(source="b")
        assert e1.event_id != e2.event_id


class TestSystemEvents:
    """Verify all 10 system events have correct event_type derivation."""

    @pytest.mark.parametrize(
        "event_cls, expected_type",
        [
            (AssetSelected, "system.asset_selected"),
            (MarketDataUpdated, "system.market_data_updated"),
            (ResearchCompleted, "system.research_completed"),
            (RiskCalculated, "system.risk_calculated"),
            (MemoryUpdated, "system.memory_updated"),
            (StrategyCreated, "system.strategy_created"),
            (BacktestCompleted, "system.backtest_completed"),
            (DecisionGenerated, "system.decision_generated"),
            (TradeRecorded, "system.trade_recorded"),
            (LearningCompleted, "system.learning_completed"),
        ],
    )
    def test_event_type(self, event_cls, expected_type):
        event = event_cls(source="test")
        assert event.event_type == expected_type


class TestInMemoryEventBus:
    """Tests for the InMemoryEventBus implementation."""

    def test_subscribe_and_publish(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe("system.asset_selected", lambda e: received.append(e))
        event = AssetSelected(source="test", payload={"symbol": "AAPL"})
        bus.publish(event)
        assert len(received) == 1
        assert received[0].payload["symbol"] == "AAPL"

    def test_wildcard_subscription(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish(AssetSelected(source="test"))
        bus.publish(MarketDataUpdated(source="test"))
        assert len(received) == 2

    def test_unsubscribe_removes_handler(self):
        bus = InMemoryEventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe("system.asset_selected", handler)
        bus.unsubscribe("system.asset_selected", handler)
        bus.publish(AssetSelected(source="test"))
        assert len(received) == 0

    def test_has_subscribers(self):
        bus = InMemoryEventBus()
        assert bus.has_subscribers("system.asset_selected") is False
        bus.subscribe("system.asset_selected", lambda e: None)
        assert bus.has_subscribers("system.asset_selected") is True

    def test_clear_removes_all_handlers(self):
        bus = InMemoryEventBus()
        bus.subscribe("system.asset_selected", lambda e: None)
        bus.subscribe("system.risk_calculated", lambda e: None)
        bus.clear()
        assert bus.has_subscribers("system.asset_selected") is False
        assert bus.has_subscribers("system.risk_calculated") is False

    def test_multiple_handlers_same_event(self):
        bus = InMemoryEventBus()
        results = []
        bus.subscribe("system.asset_selected", lambda e: results.append("a"))
        bus.subscribe("system.asset_selected", lambda e: results.append("b"))
        bus.publish(AssetSelected(source="test"))
        assert results == ["a", "b"]

    def test_handler_error_raises_event_bus_error(self):
        bus = InMemoryEventBus()
        bus.subscribe(
            "system.asset_selected",
            lambda e: (_ for _ in ()).throw(ValueError("boom")),
        )
        with pytest.raises(EventBusError, match="boom"):
            bus.publish(AssetSelected(source="test"))

    def test_class_based_handler(self):
        bus = InMemoryEventBus()
        received = []

        class MyHandler(IEventHandler):
            def handle(self, event):
                received.append(event)

        handler = MyHandler()
        bus.subscribe("system.trade_recorded", handler)
        bus.publish(TradeRecorded(source="test"))
        assert len(received) == 1

    def test_no_subscribers_no_error(self):
        bus = InMemoryEventBus()
        bus.publish(AssetSelected(source="test"))  # should not raise

    def test_unsubscribe_nonexistent_handler_no_error(self):
        bus = InMemoryEventBus()
        bus.unsubscribe("system.asset_selected", lambda e: None)  # no error
