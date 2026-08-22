"""Event contracts for the Research Data Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class DatasetRegistered(BaseEvent):
    """Fired when next dataset catalog registry entry completes."""
    pass


@dataclass(frozen=True)
class DatasetVersioned(BaseEvent):
    """Fired when dataset fingerprint revision completes."""
    pass


@dataclass(frozen=True)
class ExperimentStarted(BaseEvent):
    """Fired when strategy experiment parameters run starts."""
    pass


@dataclass(frozen=True)
class ExperimentCompleted(BaseEvent):
    """Fired when experiment metrics finalize."""
    pass


@dataclass(frozen=True)
class LineageRegistered(BaseEvent):
    """Fired when source dependency lineage node maps."""
    pass


@dataclass(frozen=True)
class QualityChecked(BaseEvent):
    """Fired when data quality score updates."""
    pass
