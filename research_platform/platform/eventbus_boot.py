"""Event bus bootloader configuring event bus singletons.
"""

from __future__ import annotations

from toji_platform.core.event_bus import InMemoryEventBus, IEventBus


class EventBusBootloader:
    """Sets up event bus singleton."""

    def boot_eventbus(self) -> IEventBus:
        return InMemoryEventBus()
