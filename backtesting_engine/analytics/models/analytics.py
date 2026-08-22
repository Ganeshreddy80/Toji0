"""Immutable Pydantic V2 models for Portfolio Analytics Foundation (Sprint 8A-H)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyticsContext(BaseModel):
    """Authoritative immutable configuration context for all analytics computations."""

    risk_free_rate: float = Field(default=0.0, description="Annualized risk-free rate ratio (e.g. 0.02 = 2%).")
    annualization_factor: float = Field(default=252.0, gt=0.0, description="Periods per year for annualizing daily/periodic returns.")
    trading_days: float = Field(default=365.0, gt=0.0, description="Calendar days per year for CAGR calculations.")
    timezone: str = Field(default="UTC", description="Target timezone for calculation timestamp evaluation.")
    decimal_precision: int = Field(default=4, ge=0, description="Output rounding precision for ratios and PnLs.")
    benchmark_name: Optional[str] = Field(default=None, description="Optional target benchmark index name.")
    benchmark_returns: List[float] = Field(default_factory=list, description="Optional benchmark periodic returns series.")
    engine_version: str = Field(default="1.0.0", description="Analytics engine version.")
    configuration_hash: str = Field(default="cfg-default-sha256", description="Configuration SHA-256 hash for reproducibility.")

    model_config = ConfigDict(frozen=True)


class EquityCurveAnalysis(BaseModel):
    """Immutable analysis of portfolio equity curve and return series."""

    equity_history: List[float] = Field(default_factory=list, description="Historical sequence of total account equity values.")
    portfolio_value_history: List[float] = Field(default_factory=list, description="Historical sequence of total portfolio mark-to-market values.")
    daily_returns: List[float] = Field(default_factory=list, description="Periodic percentage return series.")
    cumulative_returns: List[float] = Field(default_factory=list, description="Cumulative percentage returns series.")

    model_config = ConfigDict(frozen=True)


class DrawdownMetrics(BaseModel):
    """Immutable drawdown analysis metrics and drawdown curve."""

    drawdown_curve: List[float] = Field(default_factory=list, description="Sequence of peak-to-trough drawdown fractions [0.0, 1.0].")
    max_drawdown: float = Field(default=0.0, ge=0.0, le=1.0, description="Maximum peak-to-trough drawdown ratio.")
    max_drawdown_duration_seconds: float = Field(default=0.0, ge=0.0, description="Duration in seconds of the peak-to-trough drawdown phase.")
    max_recovery_duration_seconds: float = Field(default=0.0, ge=0.0, description="Duration in seconds from drawdown trough back to peak recovery.")
    peak_equity: float = Field(default=0.0, ge=0.0, description="Peak account equity reached.")
    trough_equity: float = Field(default=0.0, ge=0.0, description="Trough account equity during max drawdown.")

    model_config = ConfigDict(frozen=True)


class PerformanceMetrics(BaseModel):
    """Immutable core portfolio performance return metrics."""

    total_return: float = Field(default=0.0, description="Total net return ratio (e.g. 0.15 = 15%).")
    cagr: float = Field(default=0.0, description="Compound Annual Growth Rate.")
    annualized_return: float = Field(default=0.0, description="Annualized percentage return.")
    volatility: float = Field(default=0.0, ge=0.0, description="Annualized return standard deviation / volatility.")

    model_config = ConfigDict(frozen=True)


class RiskMetrics(BaseModel):
    """Immutable risk-adjusted return ratios."""

    sharpe_ratio: float = Field(default=0.0, description="Sharpe Ratio (Excess Return / Volatility).")
    sortino_ratio: float = Field(default=0.0, description="Sortino Ratio (Excess Return / Downside Volatility).")
    calmar_ratio: float = Field(default=0.0, description="Calmar Ratio (CAGR / Max Drawdown).")

    model_config = ConfigDict(frozen=True)


class TradeStatistics(BaseModel):
    """Immutable trade execution and profitability statistics."""

    total_trades: int = Field(default=0, ge=0, description="Total completed and open trades.")
    winning_trades: int = Field(default=0, ge=0, description="Number of profitable trades (realized_pnl > 0).")
    losing_trades: int = Field(default=0, ge=0, description="Number of loss trades (realized_pnl < 0).")
    even_trades: int = Field(default=0, ge=0, description="Number of break-even trades (realized_pnl == 0).")
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Ratio of winning trades to total trades [0.0, 1.0].")
    average_winner: float = Field(default=0.0, description="Average profit per winning trade.")
    average_loser: float = Field(default=0.0, description="Average loss per losing trade.")
    largest_winner: float = Field(default=0.0, description="Largest single trade profit.")
    largest_loser: float = Field(default=0.0, description="Largest single trade loss.")
    profit_factor: float = Field(default=0.0, ge=0.0, description="Gross Profits / Gross Losses.")
    expectancy: float = Field(default=0.0, description="Expected value per trade (PnL per trade).")
    average_holding_time_seconds: float = Field(default=0.0, ge=0.0, description="Average trade duration in seconds.")

    model_config = ConfigDict(frozen=True)


class PortfolioStatistics(BaseModel):
    """Immutable portfolio exposure, cash allocation, and turnover metrics."""

    exposure_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Time-weighted average fraction of capital invested in positions.")
    cash_pct: float = Field(default=1.0, ge=0.0, le=1.0, description="Average cash percentage of total account value.")
    invested_pct: float = Field(default=0.0, ge=0.0, le=1.0, description="Average invested percentage of total account value.")
    turnover: float = Field(default=0.0, ge=0.0, description="Portfolio turnover ratio (total traded volume / initial capital).")

    model_config = ConfigDict(frozen=True)


class SymbolPerformance(BaseModel):
    """Immutable asset-level performance metrics for Mission Control dashboard and analytics."""

    symbol: str = Field(..., description="Asset ticker symbol.")
    net_pnl: float = Field(default=0.0, description="Cumulative realized PnL.")
    return_pct: float = Field(default=0.0, description="Realized PnL as fraction of allocated capital.")
    trade_count: int = Field(default=0, ge=0, description="Total executed trades for symbol.")
    wins: int = Field(default=0, ge=0, description="Winning trades count.")
    losses: int = Field(default=0, ge=0, description="Losing trades count.")
    average_trade: float = Field(default=0.0, description="Average PnL per trade.")
    largest_win: float = Field(default=0.0, description="Largest single trade profit.")
    largest_loss: float = Field(default=0.0, description="Largest single trade loss.")
    current_drawdown: float = Field(default=0.0, ge=0.0, le=1.0, description="Current drawdown ratio for asset.")
    exposure: float = Field(default=0.0, ge=0.0, le=1.0, description="Asset position exposure ratio.")

    model_config = ConfigDict(frozen=True)


class BenchmarkComparison(BaseModel):
    """Immutable benchmark comparison metrics for multi-asset indexing."""

    benchmark_name: str = Field(..., description="Benchmark ticker or index name (e.g. S&P500, BTC).")
    beta: float = Field(default=1.0, description="Portfolio beta relative to benchmark.")
    alpha: float = Field(default=0.0, description="Annualized Jensen's alpha.")
    correlation: float = Field(default=0.0, ge=-1.0, le=1.0, description="Correlation coefficient with benchmark.")
    benchmark_total_return: float = Field(default=0.0, description="Benchmark total return ratio over period.")
    outperformance: float = Field(default=0.0, description="Excess return over benchmark (Portfolio Return - Benchmark Return).")

    model_config = ConfigDict(frozen=True)


class AnalyticsReport(BaseModel):
    """Immutable comprehensive portfolio analytics output report."""

    backtest_id: str = Field(..., description="Backtest UUID.")
    strategy_id: str = Field(default="strategy-default", description="Associated Strategy UUID / Identifier.")
    engine_version: str = Field(default="1.0.0", description="Analytics engine version.")
    configuration_hash: str = Field(default="cfg-default-sha256", description="Analytics context hash for reproducibility.")
    performance: PerformanceMetrics = Field(..., description="Performance return metrics.")
    risk: RiskMetrics = Field(..., description="Risk-adjusted return metrics.")
    trade_stats: TradeStatistics = Field(..., description="Trade execution statistics.")
    portfolio_stats: PortfolioStatistics = Field(..., description="Portfolio allocation and turnover statistics.")
    drawdown: DrawdownMetrics = Field(..., description="Drawdown curve and duration metrics.")
    equity_curve: EquityCurveAnalysis = Field(..., description="Equity history and return series.")
    degradation_detected: bool = Field(default=False, description="True if performance degradation or severe drawdown is detected for self-learning.")
    symbol_performance: Dict[str, SymbolPerformance] = Field(default_factory=dict, description="Detailed asset-level performance models for Mission Control.")
    benchmark: Optional[BenchmarkComparison] = Field(default=None, description="Optional benchmark comparison metrics.")
    context: AnalyticsContext = Field(default_factory=AnalyticsContext, description="Authoritative calculation configuration context.")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timezone-aware UTC report generation timestamp.")

    @field_validator("generated_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Enforce timezone-aware datetimes for analytics report generation."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("AnalyticsReport timestamp must be timezone-aware (e.g. UTC).")
        return v

    model_config = ConfigDict(frozen=True)
