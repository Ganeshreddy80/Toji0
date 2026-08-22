"""Domain events for Walk Forward Validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ValidationWindowCompleted(BaseEvent):
    """Fired when walk forward validation window run completes."""
    pass


@dataclass(frozen=True)
class SensitivityAnalyzed(BaseEvent):
    """Fired when parameter sensitivities analysis completes."""
    pass


@dataclass(frozen=True)
class OverfittingChecked(BaseEvent):
    """Fired when overfitting detectors run completes."""
    pass
