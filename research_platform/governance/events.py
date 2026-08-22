"""Domain events for the Governance & Audit Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PolicyEvaluated(BaseEvent):
    """Fired when compliance policy checklist evaluation runs."""
    pass


@dataclass(frozen=True)
class SignatureRegistered(BaseEvent):
    """Fired when a cryptographic signature registers."""
    pass


@dataclass(frozen=True)
class DeploymentApproved(BaseEvent):
    """Fired when strategy deployment gets authorized."""
    pass


@dataclass(frozen=True)
class AuditLogged(BaseEvent):
    """Fired when a new hash-linked audit block is appended."""
    pass
