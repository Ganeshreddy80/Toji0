"""Abstract interfaces for the Toji event system.

These ABCs define the contract for events, handlers, and the bus
itself.  Concrete implementations (e.g. ``InMemoryEventBus``) live
in sibling modules.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Callable

from toji_platform.core.types import EventId, Payload


class IEvent(abc.ABC):
    """Contract for an event that flows through the bus."""

    event_id: EventId
    event_type: str
    timestamp: datetime
    source: str
    payload: Payload




# Handler is a simple callable — no need for an ABC class.
EventHandler = Callable[[IEvent], None]
"""Signature for synchronous event handlers."""


class IEventHandler(abc.ABC):
    """Class-based event handler (alternative to bare callables)."""

    @abc.abstractmethod
    def handle(self, event: IEvent) -> None:
        """Process a received event."""


class IEventBus(abc.ABC):
    """Central publish/subscribe bus for the Toji kernel."""

    @abc.abstractmethod
    def publish(self, event: IEvent) -> None:
        """Broadcast *event* to all matching subscribers."""

    @abc.abstractmethod
    def subscribe(
        self,
        event_type: str,
        handler: EventHandler | IEventHandler,
    ) -> None:
        """Register *handler* for events of *event_type*.

        Use ``"*"`` as *event_type* to receive **all** events.
        """

    @abc.abstractmethod
    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler | IEventHandler,
    ) -> None:
        """Remove a previously registered handler."""

    @abc.abstractmethod
    def has_subscribers(self, event_type: str) -> bool:
        """Return ``True`` if at least one handler is registered."""

    @abc.abstractmethod
    def clear(self) -> None:
        """Remove all subscriptions."""
