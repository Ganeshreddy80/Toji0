"""Pydantic V2 models for the Risk Engine subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Any

from risk_engine.core.enums import RiskDecision, RiskSeverity, CircuitBreakerTriggerType


class RiskFactor(BaseModel):
    """Immutable model representing an evaluated risk checklist item."""

    id: str = Field(..., description="Unique code for the risk rule.")
    name: str = Field(..., description="Human-readable name of the risk factor.")
    severity: RiskSeverity = Field(..., description="Severity classification.")
    score: float = Field(..., description="Penalty score or localized sub-score value.")
    description: str = Field(..., description="Detailed description of the check result.")

    model_config = ConfigDict(frozen=True)


class RiskViolation(BaseModel):
    """Immutable model for a single risk rule violation."""

    rule_id: str = Field(default="UNKNOWN", description="Unique code of the violated rule.")
    severity: RiskSeverity = Field(default=RiskSeverity.HIGH, description="Severity of the violation.")
    message: str = Field(..., description="Violation message.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of violation.")

    model_config = ConfigDict(frozen=True)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.message == other
        return super().__eq__(other)

    def __contains__(self, item: str) -> bool:
        return item in self.message

    def __str__(self) -> str:
        return self.message


class AccountRisk(BaseModel):
    """Immutable model for account balance, equity, and margin risk status."""

    balance: float = Field(default=0.0, ge=0.0, description="Current account balance.")
    equity: float = Field(default=0.0, ge=0.0, description="Current equity including unrealized PnL.")
    initial_balance: float = Field(default=0.0, ge=0.0, description="Starting account balance.")
    peak_balance: float = Field(default=0.0, ge=0.0, description="Peak account balance achieved.")
    net_profit: float = Field(default=0.0, description="Net realized profit.")
    free_margin: float = Field(default=0.0, ge=0.0, description="Available margin for trading.")
    margin_usage: float = Field(default=0.0, ge=0.0, description="Locked margin in active positions.")
    leverage: float = Field(default=1.0, ge=0.0, description="Current account leverage ratio.")

    model_config = ConfigDict(frozen=True)


class PortfolioRisk(BaseModel):
    """Immutable portfolio aggregation metrics."""

    gross_exposure: float = Field(default=0.0, ge=0.0, description="Absolute sum of open position values.")
    net_exposure: float = Field(default=0.0, description="Signed sum of open position values.")
    long_exposure: float = Field(default=0.0, ge=0.0, description="Total long exposure value.")
    short_exposure: float = Field(default=0.0, ge=0.0, description="Total short exposure value.")
    open_positions_count: int = Field(default=0, ge=0, description="Number of currently active positions.")
    diversification_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Portfolio diversification score [0, 1].")
    portfolio_heat: float = Field(default=0.0, ge=0.0, description="Aggregate position risk heat score.")
    remaining_risk_budget: float = Field(default=0.0, ge=0.0, description="Available risk allocation buffer.")

    model_config = ConfigDict(frozen=True)


class PositionRisk(BaseModel):
    """Immutable risk details for a single symbol position."""

    symbol: str = Field(..., description="Ticker symbol.")
    position_size: float = Field(..., description="Position size quantity.")
    leverage: float = Field(default=1.0, ge=1.0, description="Leverage used.")
    entry_price: float = Field(..., ge=0.0, description="Average entry cost.")
    current_price: float = Field(..., ge=0.0, description="Last known mark price.")
    unrealized_pnl: float = Field(default=0.0, description="Floating profit or loss.")
    stop_loss: float | None = Field(default=None, description="Stop loss price.")
    take_profit: float | None = Field(default=None, description="Take profit price.")
    initial_margin: float = Field(default=0.0, ge=0.0, description="Initial margin locked.")
    risk_reward_ratio: float = Field(default=0.0, ge=0.0, description="Risk-to-reward ratio.")

    model_config = ConfigDict(frozen=True)


class ExposureRisk(BaseModel):
    """Immutable breakdown of portfolio exposure across dimensions."""

    symbol_exposure: dict[str, float] = Field(default_factory=dict, description="Exposure value per ticker symbol.")
    sector_exposure: dict[str, float] = Field(default_factory=dict, description="Exposure value per asset sector.")
    coin_exposure: dict[str, float] = Field(default_factory=dict, description="Exposure value per cryptocurrency.")
    stablecoin_allocation: float = Field(default=100.0, ge=0.0, le=100.0, description="Stablecoin allocation percentage.")
    exchange_exposure: dict[str, float] = Field(default_factory=dict, description="Exposure value per exchange/venue.")

    model_config = ConfigDict(frozen=True)


class DrawdownRisk(BaseModel):
    """Immutable drawdown performance indicators."""

    rolling_drawdown: float = Field(default=0.0, ge=0.0, description="Current drawdown percentage.")
    max_drawdown: float = Field(default=0.0, ge=0.0, description="Peak drawdown percentage observed.")
    peak_equity: float = Field(default=0.0, ge=0.0, description="Highest equity point achieved.")
    time_under_water: float = Field(default=0.0, ge=0.0, description="Seconds spent in drawdown.")
    recovery_factor: float = Field(default=0.0, ge=0.0, description="Net profit divided by max drawdown.")

    model_config = ConfigDict(frozen=True)


class MarginRisk(BaseModel):
    """Immutable margin call/liquidation status."""

    margin_usage_pct: float = Field(default=0.0, ge=0.0, description="Locked margin as % of equity.")
    margin_call_level: float = Field(default=0.8, ge=0.0, description="Equity % trigger level for margin call.")
    liquidation_level: float = Field(default=0.5, ge=0.0, description="Equity % trigger level for liquidation.")

    model_config = ConfigDict(frozen=True)


class LeverageRisk(BaseModel):
    """Immutable leverage usage statistics."""

    account_leverage: float = Field(default=1.0, ge=0.0, description="Portfolio leverage ratio.")
    max_leverage_limit: float = Field(default=5.0, ge=0.0, description="Maximum permitted leverage limit.")
    leverage_utilization: float = Field(default=0.0, ge=0.0, le=100.0, description="Leverage utilization percentage.")

    model_config = ConfigDict(frozen=True)


class CircuitBreakerState(BaseModel):
    """Immutable status of all system circuit breaker check rules."""

    active_breakers: list[CircuitBreakerTriggerType] = Field(default_factory=list, description="List of currently active circuit breakers.")
    halt_trading: bool = Field(default=False, description="Whether a circuit breaker is actively halting execution.")
    cooldown_until: datetime | None = Field(default=None, description="Datetime until trading is halted in cooldown.")

    model_config = ConfigDict(frozen=True)


class RiskMetrics(BaseModel):
    """Immutable risk-adjusted performance performance indices."""

    sharpe_ratio: float = Field(default=0.0, description="Annualized Sharpe ratio.")
    sortino_ratio: float = Field(default=0.0, description="Annualized Sortino ratio.")
    calmar_ratio: float = Field(default=0.0, description="Annualized Calmar ratio.")
    profit_factor: float = Field(default=0.0, ge=0.0, description="Gross profit divided by gross loss.")
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Winning trades ratio [0, 1].")
    expectancy: float = Field(default=0.0, description="Average trade net profit expectancy.")

    model_config = ConfigDict(frozen=True)


class RiskConfiguration(BaseModel):
    """Configurable thresholds for the Rules Engine."""

    daily_loss_limit: float = Field(default=0.02, description="Daily loss limit as decimal.")
    weekly_loss_limit: float = Field(default=0.05, description="Weekly loss limit as decimal.")
    monthly_loss_limit: float = Field(default=0.10, description="Monthly loss limit as decimal.")
    max_drawdown_limit: float = Field(default=0.15, description="Drawdown limit as decimal.")
    max_consecutive_losses: int = Field(default=5, description="Maximum permitted consecutive losses count.")
    max_losing_streak: int = Field(default=7, description="Maximum losing trades streak length.")
    max_open_positions: int = Field(default=10, description="Maximum open positions.")
    max_position_size: float = Field(default=100000.0, description="Maximum dollar position size allocation.")
    max_symbol_exposure: float = Field(default=50000.0, description="Maximum symbol exposure in dollars.")
    max_sector_exposure: float = Field(default=150000.0, description="Maximum sector exposure in dollars.")
    max_portfolio_exposure: float = Field(default=500000.0, description="Maximum portfolio gross exposure in dollars.")
    max_correlation_exposure: float = Field(default=0.7, description="Maximum correlation threshold.")
    max_leverage: float = Field(default=5.0, description="Max leverage limit.")
    max_margin_usage: float = Field(default=0.5, description="Max margin utilization ratio.")
    max_heat: float = Field(default=1.0, description="Max portfolio heat index.")
    max_open_risk: float = Field(default=0.05, description="Max open risk as decimal of equity.")
    max_unrealized_loss: float = Field(default=0.10, description="Max unrealized loss as decimal.")
    min_liquidity_depth: float = Field(default=10000.0, description="Minimum order depth required.")
    max_spread: float = Field(default=0.01, description="Max bid-ask spread ratio.")
    max_slippage: float = Field(default=0.02, description="Max execution slippage ratio.")
    weekend_restrictions: bool = Field(default=True, description="Enable weekend blocks.")
    market_halt: bool = Field(default=False, description="Explicit system halt status.")
    exchange_maintenance: bool = Field(default=False, description="Exchange maintenance state.")
    news_lock: bool = Field(default=False, description="News event lock block status.")
    manual_kill_switch: bool = Field(default=False, description="Manual system kill switch toggle.")
    emergency_stop: bool = Field(default=False, description="Immediate emergency stop halt.")
    cooldown_period_seconds: int = Field(default=300, description="Halt cooldown duration.")
    risk_override: bool = Field(default=False, description="Master override to bypass rules.")

    model_config = ConfigDict(frozen=True)


class RiskAssessment(BaseModel):
    """Consolidated assessment containing the overall score and final permit decision."""

    overall_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Consolidated risk safety score, starts at 100.",
    )
    decision: RiskDecision = Field(..., description="Permissibility decision (ALLOW, BLOCK, REVIEW).")
    factors: list[RiskFactor] = Field(default_factory=list, description="All evaluated risk factor details.")
    violations: list[str | RiskViolation] = Field(default_factory=list, description="List of rule violations.")

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="before")
    @classmethod
    def convert_violations(cls, data: Any) -> Any:
        if isinstance(data, dict) and "violations" in data:
            raw_violations = data["violations"]
            if isinstance(raw_violations, list):
                converted = []
                for v in raw_violations:
                    if isinstance(v, str):
                        converted.append({
                            "rule_id": "LEGACY",
                            "severity": "HIGH",
                            "message": v,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    else:
                        converted.append(v)
                data["violations"] = converted
        return data


class RiskState(BaseModel):
    """Immutable state holding the active risk assessment for a symbol and timeframe."""

    symbol: str = Field(..., description="Ticker symbol.")
    timeframe: str = Field(..., description="Target timeframe.")
    assessment: RiskAssessment = Field(..., description="Evaluated risk assessment results.")
    account_risk: AccountRisk = Field(default_factory=AccountRisk, description="Account risk metrics.")
    portfolio_risk: PortfolioRisk = Field(default_factory=PortfolioRisk, description="Portfolio risk metrics.")
    exposure_risk: ExposureRisk = Field(default_factory=ExposureRisk, description="Asset exposure risk details.")
    drawdown_risk: DrawdownRisk = Field(default_factory=DrawdownRisk, description="Equity drawdown performance indices.")
    margin_risk: MarginRisk = Field(default_factory=MarginRisk, description="Margin call/liquidation status.")
    leverage_risk: LeverageRisk = Field(default_factory=LeverageRisk, description="Leverage usage statistics.")
    circuit_breaker: CircuitBreakerState = Field(default_factory=lambda: CircuitBreakerState(halt_trading=False), description="Circuit breaker statuses.")
    metrics: RiskMetrics = Field(default_factory=RiskMetrics, description="Performance risk-adjusted index performance.")
    config: RiskConfiguration = Field(default_factory=RiskConfiguration, description="Configuration parameters utilized.")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last assessment update timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class RiskSnapshot(BaseModel):
    """Unified snapshot of risk states across multiple timeframes for a symbol."""

    snapshot_id: str = Field(..., description="Unique UUID for this snapshot.")
    symbol: str = Field(..., description="Ticker symbol.")
    timestamp: datetime = Field(..., description="Snapshot timestamp.")
    states: dict[str, RiskState] = Field(
        default_factory=dict,
        description="Timeframe mapped to timeframe-specific RiskState.",
    )

    model_config = ConfigDict(frozen=True)
