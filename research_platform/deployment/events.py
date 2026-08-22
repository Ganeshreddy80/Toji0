"""Domain events for the Deployment Manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class DeploymentTriggered(BaseEvent):
    """Fired when strategy rollout starts."""
    pass


@dataclass(frozen=True)
class DeploymentCompleted(BaseEvent):
    """Fired when rollout successfully activates."""
    pass


@dataclass(frozen=True)
class DeploymentFailed(BaseEvent):
    """Fired when health check fails or rollout crashes."""
    pass


@dataclass(frozen=True)
class DeploymentRolledBack(BaseEvent):
    """Fired when rollback executes."""
    pass
