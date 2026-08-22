"""Domain events for the Experiment Management Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ExperimentLogged(BaseEvent):
    """Fired when an experiment record registers."""
    pass


@dataclass(frozen=True)
class ReproducibilityChecked(BaseEvent):
    """Fired when validation verification checks complete."""
    pass


@dataclass(frozen=True)
class ExperimentsCompared(BaseEvent):
    """Fired when comparing multiple experiment records."""
    pass


@dataclass(frozen=True)
class ExperimentReplayed(BaseEvent):
    """Fired when an experiment replay execution triggers."""
    pass
