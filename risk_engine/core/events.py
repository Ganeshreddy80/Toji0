"""System events for the Risk Engine subsystem.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class RiskInitialized(BaseEvent):
    """Fired when the Risk Engine plugin starts successfully."""


@dataclass(frozen=True)
class RiskShutdown(BaseEvent):
    """Fired when the Risk Engine plugin shuts down."""


@dataclass(frozen=True)
class RiskUpdated(BaseEvent):
    """Fired when a risk assessment state is updated."""


@dataclass(frozen=True)
class RiskApproved(BaseEvent):
    """Fired when a risk check passes with an ALLOW decision."""


@dataclass(frozen=True)
class RiskRejected(BaseEvent):
    """Fired when a risk check results in a BLOCK decision."""


@dataclass(frozen=True)
class RiskReview(BaseEvent):
    """Fired when a risk check results in a REVIEW decision.

    REVIEW means the trade requires human-in-the-loop approval before execution.
    It is intentionally treated as a non-execution path: ExecutionApproved is NOT
    published. The downstream consumer must handle this event explicitly if conditional
    execution is desired. Under FAIL CLOSED, no execution proceeds on REVIEW.
    """


@dataclass(frozen=True)
class RiskThresholdExceeded(BaseEvent):
    """Fired when a risk metric exceeds critical threshold limits (e.g. max daily drawdowns)."""


# Sprint 7 Institutional Risk Events
@dataclass(frozen=True)
class RiskEvaluated(BaseEvent):
    """Fired when any execution request is evaluated by the rules engine."""


@dataclass(frozen=True)
class RiskLimitExceeded(BaseEvent):
    """Fired when a risk limit configuration parameter is breached."""


@dataclass(frozen=True)
class DrawdownUpdated(BaseEvent):
    """Fired when drawdown tracking metrics are updated."""


@dataclass(frozen=True)
class ExposureUpdated(BaseEvent):
    """Fired when exposure tracking metrics are updated."""


@dataclass(frozen=True)
class CircuitBreakerTriggered(BaseEvent):
    """Fired when any circuit breaker condition is triggered."""


@dataclass(frozen=True)
class CircuitBreakerReleased(BaseEvent):
    """Fired when any circuit breaker condition is released."""


@dataclass(frozen=True)
class PortfolioRiskUpdated(BaseEvent):
    """Fired when portfolio-wide risk metrics are updated."""


@dataclass(frozen=True)
class PositionRiskUpdated(BaseEvent):
    """Fired when active positions risk details are updated."""
