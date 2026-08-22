"""TOJI Quantitative Analytics Engine package.

Exposes institutional-grade performance stats, backtesting simulations,
portfolio allocation solvers, risk evaluation metrics, Monte Carlo simulations,
benchmarking engines, stress testing, and analytical report compilers.
"""

__version__ = "0.1.0"
__package_name__ = "toji-analytics"

from analytics.statistics.calculator import StatsCalculator
from analytics.backtesting.runner import StrategyRunner
from analytics.backtesting.models import Order, Trade, Position, PortfolioState
from analytics.backtesting.costs import (
    ZeroCommissionModel,
    FixedCommissionModel,
    LinearCommissionModel,
    ZeroSlippageModel,
    FixedSpreadSlippageModel,
    VolatilityScaledSlippageModel,
)
from analytics.risk_metrics.calculator import RiskMetricsCalculator
from analytics.portfolio.allocator import PortfolioAllocator
from analytics.portfolio.attribution import PerformanceAttributor
from analytics.optimization.search import GridSearch, RandomSearch, IBayesianOptimizer
from analytics.optimization.sensitivity import SensitivityAnalyzer
from analytics.monte_carlo.simulator import MonteCarloSimulator
from analytics.position_sizing.sizing import PositionSizer
from analytics.benchmarks.engine import BenchmarkEngine
from analytics.stress_testing.engine import StressTester
from analytics.reports.generator import ReportGenerator

__all__ = [
    "StatsCalculator",
    "StrategyRunner",
    "Order",
    "Trade",
    "Position",
    "PortfolioState",
    "ZeroCommissionModel",
    "FixedCommissionModel",
    "LinearCommissionModel",
    "ZeroSlippageModel",
    "FixedSpreadSlippageModel",
    "VolatilityScaledSlippageModel",
    "RiskMetricsCalculator",
    "PortfolioAllocator",
    "PerformanceAttributor",
    "GridSearch",
    "RandomSearch",
    "IBayesianOptimizer",
    "SensitivityAnalyzer",
    "MonteCarloSimulator",
    "PositionSizer",
    "BenchmarkEngine",
    "StressTester",
    "ReportGenerator",
]
