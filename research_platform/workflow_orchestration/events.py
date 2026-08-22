"""Domain events for the Workflow Orchestration Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class WorkflowStarted(BaseEvent):
    """Fired when a new workflow instance initializes."""
    pass


@dataclass(frozen=True)
class WorkflowStepTransitioned(BaseEvent):
    """Fired when state moves to another step."""
    pass


@dataclass(frozen=True)
class WorkflowStepCompleted(BaseEvent):
    """Fired when a step succeeds."""
    pass


@dataclass(frozen=True)
class WorkflowStepFailed(BaseEvent):
    """Fired when a step fails."""
    pass


@dataclass(frozen=True)
class WorkflowPaused(BaseEvent):
    """Fired when a step requires approval and pauses progress."""
    pass


@dataclass(frozen=True)
class WorkflowResumed(BaseEvent):
    """Fired when approvals resume a paused workflow."""
    pass


@dataclass(frozen=True)
class WorkflowRolledBack(BaseEvent):
    """Fired when rolling back to a previous completed step."""
    pass


@dataclass(frozen=True)
class WorkflowApprovalLogged(BaseEvent):
    """Fired when an approval signature registers."""
    pass
