"""Domain events for the Research Intelligence Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class HypothesisRegistered(BaseEvent):
    """Fired when a new research hypothesis is tracked."""
    pass


@dataclass(frozen=True)
class ResearchScored(BaseEvent):
    """Fired when an experiment completes and scores its metrics."""
    pass


@dataclass(frozen=True)
class RecommendationGenerated(BaseEvent):
    """Fired when advisory parameters adjustments generate."""
    pass


@dataclass(frozen=True)
class ResearchRanked(BaseEvent):
    """Fired when a new ranking list of hypotheses is generated."""
    pass


@dataclass(frozen=True)
class ExperimentFailed(BaseEvent):
    """Fired when an experiment fails quality criteria."""
    pass


@dataclass(frozen=True)
class ExperimentSucceeded(BaseEvent):
    """Fired when an experiment passes quality validation."""
    pass
