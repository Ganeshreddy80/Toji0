"""Event contracts for the Validation Core.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ValidationStarted(BaseEvent):
    """Fired when strategy validation run is initiated."""
    pass


@dataclass(frozen=True)
class ValidationCompleted(BaseEvent):
    """Fired when validation checks complete successfully."""
    pass


@dataclass(frozen=True)
class ValidationFailed(BaseEvent):
    """Fired when validation check fails or raises an error."""
    pass


@dataclass(frozen=True)
class DriftDetected(BaseEvent):
    """Fired when distribution or concept drift exceeds severity triggers."""
    pass


@dataclass(frozen=True)
class ResearchScoreUpdated(BaseEvent):
    """Fired when the aggregated institutional score of a strategy updates."""
    pass


@dataclass(frozen=True)
class StrategyRejected(BaseEvent):
    """Fired when a strategy fails to meet the validation bar."""
    pass


@dataclass(frozen=True)
class StrategyValidated(BaseEvent):
    """Fired when strategy is approved and ready for candidate promotion."""
    pass


@dataclass(frozen=True)
class ValidationArchived(BaseEvent):
    """Fired when past validation runs are archived."""
    pass
