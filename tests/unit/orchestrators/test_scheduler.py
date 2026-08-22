"""Unit tests for the Scheduler."""

from __future__ import annotations

import pytest

from orchestrators.scheduler.scheduler import Scheduler
from toji_platform.core.event_bus import InMemoryEventBus


def test_scheduler_ticks() -> None:
    """Verify that Scheduler dispatches correct ticks."""
    bus = InMemoryEventBus()
    sched = Scheduler(bus)

    events = []
    bus.subscribe("system.scheduler_tick", events.append)

    sched.trigger_market_open()
    sched.trigger_hourly()
    sched.trigger_end_of_day()

    assert len(events) == 3
    assert events[0].payload["tick_type"] == "market_open"
    assert events[1].payload["tick_type"] == "hourly"
    assert events[2].payload["tick_type"] == "eod"
