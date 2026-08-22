"""Domain events for the Experiment Manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ExperimentCreated(BaseEvent):
    """Fired when an experiment is first registered."""
    pass


@dataclass(frozen=True)
class ExperimentCompared(BaseEvent):
    """Fired when experiments compared analytics are compiled."""
    pass


@dataclass(frozen=True)
class ExperimentLeaderboardRanked(BaseEvent):
    """Fired when leaderboards score ranking updates occur."""
    pass
