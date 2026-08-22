"""Abstract contracts for the Portfolio Analytics & Attribution Engine.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.portfolio_analytics.models import (
    PortfolioReturn,
    PortfolioStatistics,
    StrategyAttribution,
    BenchmarkComparison,
    RiskAdjustedMetrics,
    DrawdownAnalysis,
    PortfolioAnalyticsReport,
    PortfolioSnapshot,
)


class IPortfolioAnalyticsRepository(abc.ABC):
    """Abstract contract for persisting portfolio snapshot summaries and reports."""

    @abc.abstractmethod
    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Persist a portfolio snapshot summary."""

    @abc.abstractmethod
    def list_snapshots(self) -> List[PortfolioSnapshot]:
        """List historical portfolio snapshots."""

    @abc.abstractmethod
    def save_report(self, report: PortfolioAnalyticsReport) -> None:
        """Persist an institutional report compilation."""

    @abc.abstractmethod
    def get_latest_report(self) -> Optional[PortfolioAnalyticsReport]:
        """Retrieve the latest portfolio analytics report."""


class IPortfolioAnalytics(abc.ABC):
    """Abstract contract for the core Portfolio Analytics orchestrator."""

    @abc.abstractmethod
    def compute_analytics(self) -> PortfolioAnalyticsReport:
        """Perform calculations, generate attributions, run benchmark checks, and report aggregates."""


class IPerformanceEngine(abc.ABC):
    """Abstract contract for returns and equity curve analytics."""

    @abc.abstractmethod
    def calculate_returns(self, nav_series: List[float], initial_nav: float) -> PortfolioReturn:
        """Compute CAGR, gross, and net returns."""

    @abc.abstractmethod
    def calculate_drawdown(self, nav_series: List[float]) -> DrawdownAnalysis:
        """Evaluate peak-to-trough drawdowns and recovery times."""


class IAttributionEngine(abc.ABC):
    """Abstract contract for performance returns attribution."""

    @abc.abstractmethod
    def attribute_performance(self, trades: List[Any], total_pnl: float) -> List[StrategyAttribution]:
        """Break down returns attribution per strategy and symbol."""


class IBenchmarkEngine(abc.ABC):
    """Abstract contract for relative benchmark comparisons."""

    @abc.abstractmethod
    def compare_benchmarks(self, portfolio_returns: List[float], benchmark_returns: Dict[str, List[float]]) -> List[BenchmarkComparison]:
        """Calculate Alpha, Beta, Tracking Error, and Relative Returns."""


class IReportingEngine(abc.ABC):
    """Abstract contract for formatting institutional reports."""

    @abc.abstractmethod
    def compile_report(self, report: PortfolioAnalyticsReport) -> str:
        """Format the report into JSON or text representation."""
