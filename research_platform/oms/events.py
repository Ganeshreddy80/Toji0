"""Domain events for the Institutional Order Management System (OMS).
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class OMSOrderCreated(BaseEvent):
    """Fired when an order is first parsed and added to OMS."""
    pass


@dataclass(frozen=True)
class OMSOrderStateChanged(BaseEvent):
    """Fired when an order migrates its lifecycle status."""
    pass


@dataclass(frozen=True)
class OMSOrderRouted(BaseEvent):
    """Fired when an order is routed to broker adaptors."""
    pass


@dataclass(frozen=True)
class OrderReceived(BaseEvent):
    """Fired when an order request is received by the OMS."""
    pass


@dataclass(frozen=True)
class OrderValidated(BaseEvent):
    """Fired when an order request passes validation checks."""
    pass


@dataclass(frozen=True)
class OrderRejected(BaseEvent):
    """Fired when an order request fails validation."""
    pass


@dataclass(frozen=True)
class ParentCreated(BaseEvent):
    """Fired when a parent order is created for slicing."""
    pass


@dataclass(frozen=True)
class ChildCreated(BaseEvent):
    """Fired when a sliced child order is created."""
    pass


@dataclass(frozen=True)
class OrderRouted(BaseEvent):
    """Fired when an order is routed for execution."""
    pass

