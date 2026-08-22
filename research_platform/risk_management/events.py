"""Event contracts for the Risk Management System.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class RiskEvaluationStarted(BaseEvent):
    """Fired when risk validation begins."""
    pass


@dataclass(frozen=True)
class RiskEvaluationCompleted(BaseEvent):
    """Fired when risk calculations conclude."""
    pass


@dataclass(frozen=True)
class RiskApproved(BaseEvent):
    """Fired when order complies with risk rules."""
    pass


@dataclass(frozen=True)
class RiskRejected(BaseEvent):
    """Fired when order fails validation checkpoints."""
    pass


@dataclass(frozen=True)
class RiskLimitExceeded(BaseEvent):
    """Fired when limits are breached."""
    pass


@dataclass(frozen=True)
class ExposureLimitExceeded(BaseEvent):
    """Fired when sector exposure limits are breached."""
    pass


@dataclass(frozen=True)
class DrawdownLimitExceeded(BaseEvent):
    """Fired when total session drawdown limits are breached."""
    pass


@dataclass(frozen=True)
class LeverageLimitExceeded(BaseEvent):
    """Fired when leverage caps are exceeded."""
    pass


@dataclass(frozen=True)
class MarginCallTriggered(BaseEvent):
    """Fired when available margin drops below maintenance levels."""
    pass


@dataclass(frozen=True)
class LiquidityAlert(BaseEvent):
    """Fired when slippage levels spike."""
    pass


@dataclass(frozen=True)
class ConcentrationAlert(BaseEvent):
    """Fired when asset concentration exceeds constraints."""
    pass


@dataclass(frozen=True)
class KillSwitchActivated(BaseEvent):
    """Fired when emergency kill switch pause status turns active."""
    pass


@dataclass(frozen=True)
class KillSwitchReleased(BaseEvent):
    """Fired when emergency halt status is deactivated."""
    pass


@dataclass(frozen=True)
class EmergencyLiquidationStarted(BaseEvent):
    """Fired when system begins selling off active positions."""
    pass


@dataclass(frozen=True)
class EmergencyLiquidationCompleted(BaseEvent):
    """Fired when emergency sell off closes all open records."""
    pass


@dataclass(frozen=True)
class RiskAlertGenerated(BaseEvent):
    """Fired when alerts of varying severity levels are logged."""
    pass


@dataclass(frozen=True)
class DashboardUpdated(BaseEvent):
    """Fired when metrics cache aggregates update."""
    pass
