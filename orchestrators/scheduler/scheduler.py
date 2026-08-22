"""Scheduler for dispatching system clock ticks and interval events across the TOJI platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrators.events import SchedulerTick

if TYPE_CHECKING:
    from toji_platform.core.event_bus.interfaces import IEventBus


class Scheduler:
    """Dispatches event-based interval ticks to trigger downstream orchestrators."""

    def __init__(self, event_bus: IEventBus) -> None:
        """Initialize the Scheduler.

        Args:
            event_bus: Kernel Event Bus.
        """
        self.event_bus = event_bus

    def tick(self, tick_type: str) -> None:
        """Publish a SchedulerTick event for a specific interval.

        Args:
            tick_type: Standard label ("market_open", "hourly", "funding", "economic_event", "eod", "manual").
        """
        event = SchedulerTick(
            source="Scheduler",
            tick_type=tick_type,
            payload={"tick_type": tick_type},
        )
        self.event_bus.publish(event)

    def trigger_market_open(self) -> None:
        """Trigger the Market Open interval tick."""
        self.tick("market_open")

    def trigger_hourly(self) -> None:
        """Trigger the Hourly interval tick."""
        self.tick("hourly")

    def trigger_funding_times(self) -> None:
        """Trigger the Funding Times interval tick."""
        self.tick("funding")

    def trigger_economic_event(self) -> None:
        """Trigger the Economic Event interval tick."""
        self.tick("economic_event")

    def trigger_end_of_day(self) -> None:
        """Trigger the End of Day interval tick."""
        self.tick("eod")

    def trigger_manual(self, tick_type: str) -> None:
        """Trigger a manual interval tick."""
        self.tick(tick_type)
