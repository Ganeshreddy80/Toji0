"""System events for the Portfolio Construction Engine.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PortfolioUpdated(BaseEvent):
    """Fired when portfolio construction state changes."""

    @property
    def event_type(self) -> str:
        return "system.portfolio_updated"


@dataclass(frozen=True)
class PortfolioGenerated(BaseEvent):
    """Fired when a new target portfolio decision is constructed."""

    @property
    def event_type(self) -> str:
        return "system.portfolio_generated"


@dataclass(frozen=True)
class PortfolioConstructionApproved(BaseEvent):
    """Fired when a constructed portfolio passes all constraints and is approved."""

    @property
    def event_type(self) -> str:
        return "system.portfolio_construction_approved"


@dataclass(frozen=True)
class PortfolioConstructionRejected(BaseEvent):
    """Fired when portfolio construction fails closed or violates constraints."""

    @property
    def event_type(self) -> str:
        return "system.portfolio_construction_rejected"
