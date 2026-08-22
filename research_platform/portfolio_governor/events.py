"""Event contracts for the Portfolio Governor subsystem.

All events follow the existing BaseEvent pattern:
  @dataclass(frozen=True)
  event_type auto-derived from class name as system.<snake_case>
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PortfolioDecisionCreated(BaseEvent):
    """Fired when PortfolioGovernor produces an APPROVED or REJECTED decision."""


@dataclass(frozen=True)
class GovernorPositionOpened(BaseEvent):
    """Fired when the governor records a new position after a confirmed fill."""


@dataclass(frozen=True)
class GovernorPositionUpdated(BaseEvent):
    """Fired when an existing governor position is updated (price or quantity change)."""


@dataclass(frozen=True)
class GovernorPositionClosed(BaseEvent):
    """Fired when a governed position quantity reaches zero."""
