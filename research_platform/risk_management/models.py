"""Immutable Pydantic models for the Risk Management System.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RiskConfiguration(BaseModel):
    """Sizing thresholds config for risk bounds evaluation."""

    max_drawdown: float = 0.20
    max_leverage: float = 2.0
    confidence_level: float = 0.95

    model_config = ConfigDict(frozen=True)


class RiskLimits(BaseModel):
    """Hard boundaries configuration."""

    max_position_size: float = 0.30
    max_daily_loss: float = 0.05
    max_concentration: float = 0.40

    model_config = ConfigDict(frozen=True)


class PositionRisk(BaseModel):
    """Sizing evaluations per asset positions."""

    symbol: str
    quantity: float
    stop_loss_distance: float
    margin_utilization: float

    model_config = ConfigDict(frozen=True)


class PortfolioRisk(BaseModel):
    """Aggregate risk stats."""

    gross_exposure: float
    net_exposure: float
    beta: float
    diversification_score: float

    model_config = ConfigDict(frozen=True)


class MarketRisk(BaseModel):
    """Environmental parameters checks."""

    volatility_spike: bool
    spread_widened: bool
    trading_halted: bool

    model_config = ConfigDict(frozen=True)


class ExposureReport(BaseModel):
    """Aggregated exposure stats."""

    total_exposure: float
    sector_exposures: Dict[str, float] = Field(default_factory=dict)
    exchange_exposures: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class VaRReport(BaseModel):
    """Value-at-Risk parameters."""

    parametric_var: float
    historical_var: float
    confidence_level: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class CVaRReport(BaseModel):
    """Expected Shortfall stats."""

    expected_shortfall: float
    confidence_level: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class StressScenario(BaseModel):
    """Stress scenario configurations parameters."""

    scenario_name: str
    volatility_shift: float
    correlation_shift: float

    model_config = ConfigDict(frozen=True)


class StressTestResult(BaseModel):
    """Simulation outcomes records."""

    scenario_name: str
    expected_loss: float
    passed: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class LeverageReport(BaseModel):
    """Buying power and margin usages details."""

    effective_leverage: float
    margin_used: float
    buying_power: float

    model_config = ConfigDict(frozen=True)


class LiquidityReport(BaseModel):
    """Spread slippages estimations."""

    avg_volume: float
    estimated_slippage: float
    liquidity_score: float

    model_config = ConfigDict(frozen=True)


class ConcentrationReport(BaseModel):
    """Asset concentration bounds details."""

    max_concentration: float
    imbalance_score: float

    model_config = ConfigDict(frozen=True)


class LimitViolation(BaseModel):
    """Active boundary breach report."""

    violation_id: str
    limit_name: str
    violated: bool
    details: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RiskAlert(BaseModel):
    """Notification warn signal."""

    alert_id: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    category: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RiskScore(BaseModel):
    """Aggregated safety score."""

    composite_score: float  # 0.0 to 100.0 (100.0 is safest)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class KillSwitchStatus(BaseModel):
    """Halt switch states registers."""

    activated: bool
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ComplianceReport(BaseModel):
    """Audit report details."""

    compliant: bool
    rejection_reasons: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RiskProfile(BaseModel):
    """Evaluation output."""

    var_report: VaRReport
    cvar_report: CVaRReport
    leverage_report: LeverageReport
    compliance_report: ComplianceReport

    model_config = ConfigDict(frozen=True)


class RiskEvaluation(BaseModel):
    """Sizing evaluation profile wrapper."""

    evaluation_id: str
    portfolio_id: str
    risk_score: RiskScore
    profile: RiskProfile
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RiskApproval(BaseModel):
    """Approved decision signatures."""

    approval_id: str
    approved: bool
    approver: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RiskDecision(BaseModel):
    """High-level decision wrapper."""

    decision_id: str
    evaluation: RiskEvaluation
    approval: RiskApproval

    model_config = ConfigDict(frozen=True)


class RiskSnapshot(BaseModel):
    """Instant snapshot status."""

    snapshot_id: str
    portfolio_id: str
    risk_score: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class RiskHistory(BaseModel):
    """Archived snapshots list."""

    history_id: str
    snapshots: List[RiskSnapshot] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PortfolioExposure(BaseModel):
    """Exposures wrapper."""

    symbol: str
    net_exposure: float
    gross_exposure: float

    model_config = ConfigDict(frozen=True)


class MarginStatus(BaseModel):
    """Equity status wrapper."""

    margin_ratio: float
    liquidating: bool

    model_config = ConfigDict(frozen=True)


class EmergencyAction(BaseModel):
    """Liquidation instructions wrapper."""

    action_id: str
    action_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class DashboardMetrics(BaseModel):
    """Aggregated stats wrapper."""

    risk_score: float
    var_95: float
    cvar_95: float
    open_alerts_count: int

    model_config = ConfigDict(frozen=True)
