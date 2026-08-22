"""Tests for the universe scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, call

from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.core.event_bus.interfaces import IEventBus
from universe.core.models import UniverseConfig
from universe.scheduler.scheduler import UniverseScheduler


class MockEventBus(IEventBus):
    """Simple mock event bus for scheduler tests."""

    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def publish(self, event) -> None:
        event_type = event.event_type if hasattr(event, "event_type") else ""
        for handler in self._handlers.get(event_type, []):
            handler(event)

    def subscribe(self, event_type: str, handler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def has_subscribers(self, event_type: str) -> bool:
        return bool(self._handlers.get(event_type))

    def clear(self) -> None:
        self._handlers.clear()


class TestUniverseScheduler:
    """Test periodic scan scheduling."""

    def test_trigger_scan_calls_callback(self) -> None:
        callback = MagicMock()
        bus = MockEventBus()
        scheduler = UniverseScheduler(bus, callback)
        scheduler.trigger_scan()
        callback.assert_called_once()

    def test_scan_count_increments(self) -> None:
        callback = MagicMock()
        bus = MockEventBus()
        scheduler = UniverseScheduler(bus, callback)
        assert scheduler.scan_count == 0
        scheduler.trigger_scan()
        assert scheduler.scan_count == 1
        scheduler.trigger_scan()
        assert scheduler.scan_count == 2

    def test_last_scan_updated(self) -> None:
        callback = MagicMock()
        bus = MockEventBus()
        scheduler = UniverseScheduler(bus, callback)
        assert scheduler.last_scan is None
        scheduler.trigger_scan()
        assert scheduler.last_scan is not None

    def test_disabled_scheduler_skips_scan(self) -> None:
        callback = MagicMock()
        bus = MockEventBus()
        scheduler = UniverseScheduler(bus, callback)
        scheduler.stop()
        scheduler.trigger_scan()
        callback.assert_not_called()

    def test_tick_respects_interval(self) -> None:
        callback = MagicMock()
        bus = MockEventBus()
        config = UniverseConfig(scan_interval_seconds=3600)
        scheduler = UniverseScheduler(bus, callback, config=config)
        scheduler.start()

        # Simulate a tick
        tick_event = BaseEvent(source="test")
        scheduler._on_tick(tick_event)
        assert callback.call_count == 1

        # Second tick too soon — should be skipped
        scheduler._on_tick(tick_event)
        assert callback.call_count == 1

    def test_start_subscribes_to_event(self) -> None:
        bus = MockEventBus()
        callback = MagicMock()
        scheduler = UniverseScheduler(bus, callback)
        scheduler.start()
        assert bus.has_subscribers("system.scheduler_tick")

    def test_stop_unsubscribes(self) -> None:
        bus = MockEventBus()
        callback = MagicMock()
        scheduler = UniverseScheduler(bus, callback)
        scheduler.start()
        scheduler.stop()
        assert not bus.has_subscribers("system.scheduler_tick")

    def test_failed_callback_doesnt_crash(self) -> None:
        callback = MagicMock(side_effect=RuntimeError("boom"))
        bus = MockEventBus()
        scheduler = UniverseScheduler(bus, callback)
        # Should not raise
        scheduler.trigger_scan()
        assert scheduler.scan_count == 0
