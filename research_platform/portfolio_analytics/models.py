"""Immutable Pydantic models for the Portfolio Analytics & Attribution Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PortfolioSnapshot(BaseModel):
    """Snapshot card summarizing portfolio active allocations."""

    timestamp: datetime
    net_asset_value: float
    cash: float
    exposure: float
    allocation_pct: float

    model_config = ConfigDict(frozen=True)


class PortfolioReturn(BaseModel):
    """Calculated returns over various horizons."""

    total_return: float
    net_return: float
    gross_return: float
    cagr: float

    model_config = ConfigDict(frozen=True)


class PortfolioStatistics(BaseModel):
    """Portfolio metrics distributions."""

    average_return: float
    median_return: float
    standard_deviation: float
    volatility: float

    model_config = ConfigDict(frozen=True)


class StrategyPerformance(BaseModel):
    """Performance cards per strategy ID."""

    strategy_id: str
    total_trades: int
    win_rate: float
    pnl: float

    model_config = ConfigDict(frozen=True)


class StrategyAttribution(BaseModel):
    """Performance returns attribution card."""

    strategy_id: str
    allocation_pct: float
    contribution_pnl: float
    risk_contribution_pct: float

    model_config = ConfigDict(frozen=True)


class SymbolPerformance(BaseModel):
    """Symbol-level performance metrics."""

    symbol: str
    total_trades: int
    win_rate: float
    pnl: float

    model_config = ConfigDict(frozen=True)


class ExchangePerformance(BaseModel):
    """Exchange-level attribution."""

    exchange: str
    pnl: float

    model_config = ConfigDict(frozen=True)


class MarketRegimePerformance(BaseModel):
    """Market regime attribution."""

    regime: str
    pnl: float

    model_config = ConfigDict(frozen=True)


class HourlyPerformance(BaseModel):
    """Hourly return breakdowns."""

    hour: int
    pnl: float

    model_config = ConfigDict(frozen=True)


class DailyPerformance(BaseModel):
    """Daily returns tracking logs."""

    date: str
    pnl: float

    model_config = ConfigDict(frozen=True)


class MonthlyPerformance(BaseModel):
    """Monthly returns tracking logs."""

    month: str
    pnl: float

    model_config = ConfigDict(frozen=True)


class BenchmarkComparison(BaseModel):
    """Relative metrics comparisons against asset benchmarks."""

    benchmark_name: str
    alpha: float
    beta: float
    tracking_error: float
    information_ratio: float
    capture_ratio: float
    correlation: float
    relative_return: float

    model_config = ConfigDict(frozen=True)


class RiskAdjustedMetrics(BaseModel):
    """Risk adjusted returns KPIs."""

    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    treynor_ratio: float
    profit_factor: float
    recovery_factor: float
    ulcer_index: float
    mar_ratio: float
    var_95: float
    cvar_95: float
    tail_risk: float
    expected_shortfall: float
    expectancy: float
    kelly_fraction: float

    model_config = ConfigDict(frozen=True)


class DrawdownAnalysis(BaseModel):
    """Drawdown periods evaluation metrics."""

    max_drawdown: float
    recovery_time_sec: float
    drawdown_duration_sec: float

    model_config = ConfigDict(frozen=True)


class RollingStatistics(BaseModel):
    """Rolling statistics values calculated over a specified window."""

    window_size: int
    rolling_returns: List[float] = Field(default_factory=list)
    rolling_volatility: List[float] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PortfolioAnalyticsReport(BaseModel):
    """Unified institutional performance analytics report."""

    report_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    returns: PortfolioReturn
    statistics: PortfolioStatistics
    risk_metrics: RiskAdjustedMetrics
    drawdown: DrawdownAnalysis
    attributions: List[StrategyAttribution] = Field(default_factory=list)
    benchmarks: List[BenchmarkComparison] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PortfolioDashboard(BaseModel):
    """Operations center dashboard cards representation."""

    portfolio_card: Dict[str, Any] = Field(default_factory=dict)
    performance_card: Dict[str, Any] = Field(default_factory=dict)
    benchmark_card: Dict[str, Any] = Field(default_factory=dict)
    risk_card: Dict[str, Any] = Field(default_factory=dict)
    strategy_card: Dict[str, Any] = Field(default_factory=dict)
    drawdown_card: Dict[str, Any] = Field(default_factory=dict)
    heatmap_card: Dict[str, Any] = Field(default_factory=dict)
    rolling_statistics_card: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PerformanceTimeline(BaseModel):
    """Timeline entry coordinate of portfolio values."""

    timestamp: datetime
    nav: float
    pnl: float

    model_config = ConfigDict(frozen=True)


class EquityCurve(BaseModel):
    """Equity curve history collection."""

    points: List[PerformanceTimeline] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ReturnSeries(BaseModel):
    """Return values distribution list."""

    timestamps: List[datetime] = Field(default_factory=list)
    returns: List[float] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ExposureBreakdown(BaseModel):
    """Portfolio net exposure values."""

    long_exposure: float
    short_exposure: float
    net_exposure: float
    gross_exposure: float

    model_config = ConfigDict(frozen=True)


class AllocationBreakdown(BaseModel):
    """Portfolio asset class allocation weights."""

    allocations: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
