"""Domain events for the Portfolio Analytics & Attribution Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PortfolioAnalyticsUpdated(BaseEvent):
    """Fired when portfolio performance calculations update."""
    pass


@dataclass(frozen=True)
class BenchmarkComparisonCompleted(BaseEvent):
    """Fired when relative benchmark indices match finishes."""
    pass


@dataclass(frozen=True)
class AttributionCompleted(BaseEvent):
    """Fired when returns attributions complete."""
    pass


@dataclass(frozen=True)
class PerformanceReportGenerated(BaseEvent):
    """Fired when an institutional report compiles."""
    pass


@dataclass(frozen=True)
class RiskMetricsUpdated(BaseEvent):
    """Fired when Sharpe/Sortino/VaR metrics are refreshed."""
    pass


@dataclass(frozen=True)
class PortfolioDashboardUpdated(BaseEvent):
    """Fired when operations center dashboard states refresh."""
    pass
