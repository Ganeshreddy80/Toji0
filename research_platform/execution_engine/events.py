"""Event contracts for the Execution Management System (EMS).
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ExchangeConnected(BaseEvent):
    """Fired when REST/WebSocket connection to exchange establishes."""
    pass


@dataclass(frozen=True)
class ExchangeDisconnected(BaseEvent):
    """Fired when exchange heartbeat disconnect is detected."""
    pass


@dataclass(frozen=True)
class OrderSubmitted(BaseEvent):
    """Fired when order leaves REST endpoints to exchange."""
    pass


@dataclass(frozen=True)
class OrderAcknowledged(BaseEvent):
    """Fired when exchange reports order ID receipt."""
    pass


@dataclass(frozen=True)
class OrderRejected(BaseEvent):
    """Fired when exchange rejects order validation."""
    pass


@dataclass(frozen=True)
class PartialFillReceived(BaseEvent):
    """Fired when partial execution fills updates arrive."""
    pass


@dataclass(frozen=True)
class FillReceived(BaseEvent):
    """Fired when full execution fills arrive."""
    pass


@dataclass(frozen=True)
class PositionUpdated(BaseEvent):
    """Fired when asset positions balance updates."""
    pass


@dataclass(frozen=True)
class BalanceUpdated(BaseEvent):
    """Fired when capital balance updates."""
    pass


@dataclass(frozen=True)
class FundingUpdated(BaseEvent):
    """Fired when funding fees settle on leverage positions."""
    pass


@dataclass(frozen=True)
class HealthAlert(BaseEvent):
    """Fired when latency thresholds exceed boundaries."""
    pass


@dataclass(frozen=True)
class ReconciliationCompleted(BaseEvent):
    """Fired when local-exchange state reconciliation completes."""
    pass


@dataclass(frozen=True)
class ExecutionCompleted(BaseEvent):
    """Fired when total order cycle finishes."""
    pass
