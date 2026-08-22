"""Domain events for the System Validation Framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ValidationStarted(BaseEvent):
    """Fired when validation workflow run initialized."""
    pass


@dataclass(frozen=True)
class SubsystemValidated(BaseEvent):
    """Fired when individual component validations execute."""
    pass


@dataclass(frozen=True)
class WorkflowStepExecuted(BaseEvent):
    """Fired when a step inside the E2E workflow registers."""
    pass


@dataclass(frozen=True)
class PlatformCertified(BaseEvent):
    """Fired when final platform certification signs successfully."""
    pass
