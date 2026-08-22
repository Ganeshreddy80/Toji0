"""Portfolio Analytics package initialization (Sprint 8A-H)."""

from backtesting_engine.analytics.benchmark import DefaultBenchmarkProvider, IBenchmarkProvider
from backtesting_engine.analytics.degradation import DefaultRuleBasedDegradationDetector, IDegradationDetector
from backtesting_engine.analytics.drawdown import DrawdownEngine
from backtesting_engine.analytics.equity_curve import EquityCurveEngine
from backtesting_engine.analytics.metrics_engine import (
    IPortfolioAnalyticsEngine,
    PortfolioAnalyticsEngine,
)
from backtesting_engine.analytics.models.analytics import (
    AnalyticsContext,
    AnalyticsReport,
    BenchmarkComparison,
    DrawdownMetrics,
    EquityCurveAnalysis,
    PerformanceMetrics,
    PortfolioStatistics,
    RiskMetrics,
    SymbolPerformance,
    TradeStatistics,
)
from backtesting_engine.analytics.performance_metrics import PerformanceMetricsEngine
from backtesting_engine.analytics.portfolio_statistics import PortfolioStatisticsEngine
from backtesting_engine.analytics.risk_metrics import (
    CalmarRatioCalculator,
    IRiskMetricCalculator,
    RiskMetricsEngine,
    SharpeRatioCalculator,
    SortinoRatioCalculator,
)
from backtesting_engine.analytics.trade_statistics import TradeStatisticsEngine

__all__ = [
    "AnalyticsContext",
    "AnalyticsReport",
    "BenchmarkComparison",
    "CalmarRatioCalculator",
    "DefaultBenchmarkProvider",
    "DefaultRuleBasedDegradationDetector",
    "DrawdownEngine",
    "DrawdownMetrics",
    "EquityCurveAnalysis",
    "EquityCurveEngine",
    "IBenchmarkProvider",
    "IDegradationDetector",
    "IPortfolioAnalyticsEngine",
    "IRiskMetricCalculator",
    "PerformanceMetrics",
    "PerformanceMetricsEngine",
    "PortfolioAnalyticsEngine",
    "PortfolioStatistics",
    "PortfolioStatisticsEngine",
    "RiskMetrics",
    "RiskMetricsEngine",
    "SharpeRatioCalculator",
    "SortinoRatioCalculator",
    "SymbolPerformance",
    "TradeStatistics",
    "TradeStatisticsEngine",
]
