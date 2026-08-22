"""Domain events for the Research Lab.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ResearchSessionStarted(BaseEvent):
    """Fired when research session initializes."""
    pass


@dataclass(frozen=True)
class FeatureExtracted(BaseEvent):
    """Fired when features are computed."""
    pass


@dataclass(frozen=True)
class FactorCalculated(BaseEvent):
    """Fired when factors are calculated."""
    pass


@dataclass(frozen=True)
class HypothesisVerified(BaseEvent):
    """Fired when a research hypothesis is verified."""
    pass
