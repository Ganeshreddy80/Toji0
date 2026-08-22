"""Comprehensive unit and integration tests for Sprint 8A-H Portfolio Analytics Hardening."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from backtesting_engine.analytics.benchmark import DefaultBenchmarkProvider, IBenchmarkProvider
from backtesting_engine.analytics.degradation import DefaultRuleBasedDegradationDetector, IDegradationDetector
from backtesting_engine.analytics.drawdown import DrawdownEngine
from backtesting_engine.analytics.equity_curve import EquityCurveEngine
from backtesting_engine.analytics.metrics_engine import PortfolioAnalyticsEngine
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
from backtesting_engine.core.enums import PositionSide, ReplayStatus, TradeStatus
from backtesting_engine.core.models import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    SimulatedFill,
    TradeRecord,
)


def create_sample_snapshots(equity_values: list[float], start_date: datetime | None = None) -> list[EquityPoint]:
    base_time = start_date or datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    snapshots = []
    initial = equity_values[0] if equity_values else 100000.0
    for idx, eq in enumerate(equity_values):
        snapshots.append(
            EquityPoint(
                timestamp=base_time + timedelta(days=idx),
                balance=eq,
                equity=eq,
                drawdown=0.0,
                open_pnl=0.0,
                closed_pnl=eq - initial,
                account_value=eq,
            )
        )
    return snapshots


# ============================================================================
# 1. Empty Portfolio Tests
# ============================================================================

def test_analytics_empty_portfolio():
    engine = PortfolioAnalyticsEngine()
    report = engine.compute_from_components(
        backtest_id="test-empty",
        snapshots=[],
        trades=[],
        fills=[],
    )

    assert report.backtest_id == "test-empty"
    assert report.performance.total_return == 0.0
    assert report.performance.cagr == 0.0
    assert report.risk.sharpe_ratio == 0.0
    assert report.trade_stats.total_trades == 0
    assert report.portfolio_stats.turnover == 0.0
    assert report.drawdown.max_drawdown == 0.0


def test_trade_stats_empty_trades():
    stats = TradeStatisticsEngine.calculate([])
    assert stats.total_trades == 0
    assert stats.winning_trades == 0
    assert stats.losing_trades == 0
    assert stats.win_rate == 0.0
    assert stats.profit_factor == 0.0
    assert stats.expectancy == 0.0


def test_equity_curve_empty_snapshots():
    eq_analysis = EquityCurveEngine.calculate([], initial_capital=100000.0)
    assert eq_analysis.equity_history == [100000.0]
    assert eq_analysis.daily_returns == []
    assert eq_analysis.cumulative_returns == [0.0]


# ============================================================================
# 2. Single Trade Tests
# ============================================================================

def test_analytics_single_winning_trade():
    engine = PortfolioAnalyticsEngine()
    now = datetime.now(timezone.utc)
    trade = TradeRecord(
        trade_id="tr-1",
        order_id="ord-1",
        symbol="BTC/USDT",
        side=PositionSide.LONG,
        entry_price=50000.0,
        exit_price=55000.0,
        quantity=1.0,
        realized_pnl=5000.0,
        status=TradeStatus.CLOSED,
        opened_at=now - timedelta(hours=2),
        closed_at=now,
    )
    snapshots = create_sample_snapshots([100000.0, 105000.0])

    report = engine.compute_from_components(
        backtest_id="test-single-win",
        snapshots=snapshots,
        trades=[trade],
        fills=[],
    )

    assert report.trade_stats.total_trades == 1
    assert report.trade_stats.winning_trades == 1
    assert report.trade_stats.losing_trades == 0
    assert report.trade_stats.win_rate == 1.0
    assert report.trade_stats.average_winner == 5000.0
    assert report.trade_stats.profit_factor == 5000.0
    assert report.trade_stats.average_holding_time_seconds == 7200.0

    sym_perf = report.symbol_performance["BTC/USDT"]
    assert isinstance(sym_perf, SymbolPerformance)
    assert sym_perf.net_pnl == 5000.0
    assert sym_perf.trade_count == 1
    assert sym_perf.wins == 1


def test_analytics_single_losing_trade():
    now = datetime.now(timezone.utc)
    trade = TradeRecord(
        trade_id="tr-2",
        order_id="ord-2",
        symbol="ETH/USDT",
        side=PositionSide.LONG,
        entry_price=3000.0,
        exit_price=2700.0,
        quantity=2.0,
        realized_pnl=-600.0,
        status=TradeStatus.CLOSED,
        opened_at=now - timedelta(minutes=30),
        closed_at=now,
    )

    stats = TradeStatisticsEngine.calculate([trade])
    assert stats.total_trades == 1
    assert stats.winning_trades == 0
    assert stats.losing_trades == 1
    assert stats.win_rate == 0.0
    assert stats.average_loser == -600.0
    assert stats.profit_factor == 0.0
    assert stats.expectancy == -600.0


# ============================================================================
# 3. Multiple Trades & Winning/Losing Strategies
# ============================================================================

def test_analytics_winning_strategy():
    trades = [
        TradeRecord(trade_id=f"tr-{i}", order_id=f"ord-{i}", symbol="BTC/USDT", side=PositionSide.LONG, entry_price=50000.0, exit_price=51000.0, quantity=1.0, realized_pnl=1000.0, status=TradeStatus.CLOSED)
        for i in range(10)
    ]
    stats = TradeStatisticsEngine.calculate(trades)

    assert stats.total_trades == 10
    assert stats.winning_trades == 10
    assert stats.losing_trades == 0
    assert stats.win_rate == 1.0
    assert stats.average_winner == 1000.0
    assert stats.expectancy == 1000.0


def test_analytics_losing_strategy():
    trades = [
        TradeRecord(trade_id=f"tr-{i}", order_id=f"ord-{i}", symbol="BTC/USDT", side=PositionSide.LONG, entry_price=50000.0, exit_price=49000.0, quantity=1.0, realized_pnl=-1000.0, status=TradeStatus.CLOSED)
        for i in range(10)
    ]
    stats = TradeStatisticsEngine.calculate(trades)

    assert stats.total_trades == 10
    assert stats.winning_trades == 0
    assert stats.losing_trades == 10
    assert stats.win_rate == 0.0
    assert stats.average_loser == -1000.0
    assert stats.expectancy == -1000.0


def test_profit_factor_calculation():
    t_win = TradeRecord(trade_id="t1", order_id="o1", symbol="BTC/USDT", side=PositionSide.LONG, entry_price=100.0, exit_price=150.0, quantity=1.0, realized_pnl=3000.0, status=TradeStatus.CLOSED)
    t_loss = TradeRecord(trade_id="t2", order_id="o2", symbol="BTC/USDT", side=PositionSide.LONG, entry_price=100.0, exit_price=90.0, quantity=1.0, realized_pnl=-1000.0, status=TradeStatus.CLOSED)

    stats = TradeStatisticsEngine.calculate([t_win, t_loss])
    assert stats.profit_factor == 3.0
    assert stats.win_rate == 0.5
    assert stats.expectancy == 1000.0


# ============================================================================
# 4. Zero Volatility & Zero Trades Tests
# ============================================================================

def test_zero_volatility_flat_equity():
    snapshots = create_sample_snapshots([100000.0, 100000.0, 100000.0, 100000.0])
    eq_curve = EquityCurveEngine.calculate(snapshots)
    perf = PerformanceMetricsEngine.calculate(snapshots, eq_curve.daily_returns)
    risk = RiskMetricsEngine().calculate(perf, eq_curve.daily_returns, max_drawdown=0.0)

    assert perf.volatility == 0.0
    assert perf.total_return == 0.0
    assert risk.sharpe_ratio == 0.0
    assert risk.sortino_ratio == 0.0
    assert risk.calmar_ratio == 0.0


def test_zero_trades_with_equity_growth():
    snapshots = create_sample_snapshots([100000.0, 102000.0, 104000.0])
    engine = PortfolioAnalyticsEngine()
    report = engine.compute_from_components(
        backtest_id="test-zero-trades",
        snapshots=snapshots,
        trades=[],
        fills=[],
    )

    assert report.trade_stats.total_trades == 0
    assert report.performance.total_return == 0.04
    assert report.portfolio_stats.turnover == 0.0


# ============================================================================
# 5. Drawdown Engine Tests
# ============================================================================

def test_drawdown_calculation_peak_and_trough():
    snapshots = create_sample_snapshots([100000.0, 120000.0, 100000.0, 90000.0, 110000.0, 125000.0])
    dd_metrics = DrawdownEngine.calculate(snapshots, initial_capital=100000.0)

    assert dd_metrics.max_drawdown == 0.25
    assert dd_metrics.peak_equity == 120000.0
    assert dd_metrics.trough_equity == 90000.0
    assert dd_metrics.max_drawdown_duration_seconds == 2 * 86400.0
    assert dd_metrics.max_recovery_duration_seconds == 2 * 86400.0


def test_drawdown_no_drawdown():
    snapshots = create_sample_snapshots([100000.0, 110000.0, 120000.0, 130000.0])
    dd_metrics = DrawdownEngine.calculate(snapshots)

    assert dd_metrics.max_drawdown == 0.0
    assert dd_metrics.max_drawdown_duration_seconds == 0.0
    assert dd_metrics.max_recovery_duration_seconds == 0.0


# ============================================================================
# 6. Performance & Risk Metrics Mathematical Correctness
# ============================================================================

def test_cagr_calculation_exact_math():
    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end_date = start_date + timedelta(days=365)
    snapshots = [
        EquityPoint(timestamp=start_date, balance=100000.0, equity=100000.0, account_value=100000.0),
        EquityPoint(timestamp=end_date, balance=120000.0, equity=120000.0, account_value=120000.0),
    ]

    eq_curve = EquityCurveEngine.calculate(snapshots, initial_capital=100000.0)
    perf = PerformanceMetricsEngine.calculate(snapshots, eq_curve.daily_returns, initial_capital=100000.0)

    assert perf.total_return == 0.20
    assert abs(perf.cagr - 0.20) < 1e-4


def test_sharpe_and_sortino_ratio_math():
    snapshots = create_sample_snapshots([100000.0, 102000.0, 101000.0, 105000.0, 104000.0, 108000.0])
    eq_curve = EquityCurveEngine.calculate(snapshots)
    perf = PerformanceMetricsEngine.calculate(snapshots, eq_curve.daily_returns)
    risk = RiskMetricsEngine().calculate(perf, eq_curve.daily_returns, max_drawdown=0.05)

    assert risk.sharpe_ratio > 0.0
    assert risk.sortino_ratio > 0.0
    assert risk.calmar_ratio > 0.0


def test_calmar_ratio_zero_drawdown():
    perf = PerformanceMetrics(cagr=0.15)
    risk = RiskMetricsEngine().calculate(perf, daily_returns=[0.01, 0.01], max_drawdown=0.0)
    assert risk.calmar_ratio == 0.0


# ============================================================================
# 7. Portfolio Statistics & Turnover Tests
# ============================================================================

def test_portfolio_statistics_turnover_and_exposure():
    snapshots = [
        EquityPoint(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), balance=80000.0, equity=100000.0, account_value=100000.0),
        EquityPoint(timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc), balance=50000.0, equity=100000.0, account_value=100000.0),
    ]
    fills = [
        SimulatedFill(order_id="o1", symbol="BTC/USDT", side=PositionSide.LONG, fill_quantity=1.0, fill_price=50000.0),
        SimulatedFill(order_id="o2", symbol="BTC/USDT", side=PositionSide.SHORT, fill_quantity=1.0, fill_price=55000.0),
    ]

    p_stats = PortfolioStatisticsEngine.calculate(snapshots, fills, initial_capital=100000.0)

    assert p_stats.turnover == 1.05
    assert p_stats.cash_pct == 0.65
    assert p_stats.invested_pct == 0.35


# ============================================================================
# 8. Open/Closed Principle Extension Tests
# ============================================================================

class CustomRatioCalculator(IRiskMetricCalculator):
    def calculate(self, performance: PerformanceMetrics, daily_returns: list[float], max_drawdown: float, context: AnalyticsContext) -> float:
        return 999.0


def test_open_closed_risk_metric_extension():
    engine = RiskMetricsEngine(sharpe_calc=CustomRatioCalculator())
    perf = PerformanceMetrics(annualized_return=0.10, volatility=0.05)
    risk = engine.calculate(perf, [0.01, 0.02], max_drawdown=0.05)

    assert risk.sharpe_ratio == 999.0


# ============================================================================
# 9. CTO Finding 1 & 3: AnalyticsContext & Risk-Free Rate Propagation
# ============================================================================

def test_analytics_context_risk_free_rate_propagation():
    ctx = AnalyticsContext(risk_free_rate=0.04, annualization_factor=252.0)
    perf = PerformanceMetrics(annualized_return=0.10, volatility=0.10)
    risk = RiskMetricsEngine().calculate(perf, [0.001, -0.0005, 0.002], max_drawdown=0.05, context=ctx)

    # Sharpe = (0.10 - 0.04) / 0.10 = 0.60
    assert abs(risk.sharpe_ratio - 0.60) < 1e-3


def test_analytics_context_custom_annualization_and_precision():
    ctx = AnalyticsContext(annualization_factor=365.0, decimal_precision=2)
    snapshots = create_sample_snapshots([100000.0, 101000.0, 102000.0])
    eq_curve = EquityCurveEngine.calculate(snapshots, context=ctx)
    perf = PerformanceMetricsEngine.calculate(snapshots, eq_curve.daily_returns, context=ctx)

    assert perf.annualized_return == round((sum(eq_curve.daily_returns) / len(eq_curve.daily_returns)) * 365.0, 2)


# ============================================================================
# 10. CTO Finding 4 & 9: Metadata & Timezone Awareness
# ============================================================================

def test_report_metadata_and_utc_timezone_awareness():
    engine = PortfolioAnalyticsEngine()
    ctx = AnalyticsContext(engine_version="2.0.0", configuration_hash="hash-123")
    report = engine.compute_from_components("bt-meta-test", [], [], [], context=ctx)

    assert report.engine_version == "2.0.0"
    assert report.configuration_hash == "hash-123"
    assert report.generated_at.tzinfo is not None
    assert report.generated_at.tzinfo == timezone.utc


# ============================================================================
# 11. CTO Finding 5: SymbolPerformance Model
# ============================================================================

def test_symbol_performance_model_structure():
    trades = [
        TradeRecord(trade_id="t1", order_id="o1", symbol="BTC/USDT", side=PositionSide.LONG, entry_price=50000.0, exit_price=52000.0, quantity=1.0, realized_pnl=2000.0, status=TradeStatus.CLOSED),
        TradeRecord(trade_id="t2", order_id="o2", symbol="ETH/USDT", side=PositionSide.LONG, entry_price=3000.0, exit_price=2900.0, quantity=2.0, realized_pnl=-200.0, status=TradeStatus.CLOSED),
        TradeRecord(trade_id="t3", order_id="o3", symbol="BTC/USDT", side=PositionSide.LONG, entry_price=52000.0, exit_price=53000.0, quantity=1.0, realized_pnl=1000.0, status=TradeStatus.CLOSED),
    ]

    engine = PortfolioAnalyticsEngine()
    report = engine.compute_from_components("test-symbols-model", [], trades, [])

    btc_perf = report.symbol_performance["BTC/USDT"]
    eth_perf = report.symbol_performance["ETH/USDT"]

    assert isinstance(btc_perf, SymbolPerformance)
    assert btc_perf.net_pnl == 3000.0
    assert btc_perf.trade_count == 2
    assert btc_perf.wins == 2
    assert btc_perf.losses == 0

    assert isinstance(eth_perf, SymbolPerformance)
    assert eth_perf.net_pnl == -200.0
    assert eth_perf.trade_count == 1
    assert eth_perf.losses == 1


# ============================================================================
# 12. CTO Finding 6: IDegradationDetector Interface & Custom Injection
# ============================================================================

class CustomDegradationDetector(IDegradationDetector):
    def detect_degradation(self, drawdown: DrawdownMetrics, trade_stats: TradeStatistics, risk: RiskMetrics, context: AnalyticsContext) -> bool:
        return True  # Always trigger for testing injection


def test_degradation_detector_interface_injection():
    engine = PortfolioAnalyticsEngine(degradation_detector=CustomDegradationDetector())
    report = engine.compute_from_components("test-deg-custom", [], [], [])

    assert report.degradation_detected is True


def test_default_rule_based_degradation_detector():
    detector = DefaultRuleBasedDegradationDetector(max_drawdown_threshold=0.20)
    ctx = AnalyticsContext()

    dd_high = DrawdownMetrics(max_drawdown=0.25)
    t_stats = TradeStatistics(total_trades=2, win_rate=0.5)
    risk = RiskMetrics(sharpe_ratio=1.5)

    assert detector.detect_degradation(dd_high, t_stats, risk, ctx) is True


# ============================================================================
# 13. CTO Finding 7: IBenchmarkProvider Interface & Comparison
# ============================================================================

def test_benchmark_provider_architecture():
    ctx = AnalyticsContext(
        benchmark_name="SPY",
        benchmark_returns=[0.01, 0.02, -0.01, 0.015, 0.005],
    )
    provider = DefaultBenchmarkProvider()

    comp = provider.calculate_benchmark_comparison(
        portfolio_returns=[0.012, 0.018, -0.005, 0.02, 0.01],
        portfolio_total_return=0.055,
        context=ctx,
    )

    assert comp is not None
    assert isinstance(comp, BenchmarkComparison)
    assert comp.benchmark_name == "SPY"
    assert comp.beta > 0.0
    assert comp.outperformance != 0.0


# ============================================================================
# 14. End-to-End BacktestResult Integration & Immutability
# ============================================================================

def test_compute_analytics_from_backtest_result_with_context():
    config = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 10, tzinfo=timezone.utc), initial_capital=100000.0)
    snapshots = create_sample_snapshots([100000.0, 105000.0, 110000.0])
    result = BacktestResult(
        backtest_id="bt-full-run-h",
        config=config,
        replay_session_id="sess-1",
        status=ReplayStatus.COMPLETED,
        equity_snapshots=snapshots,
        trades=[],
        fills=[],
        final_equity=110000.0,
    )

    ctx = AnalyticsContext(risk_free_rate=0.02)
    engine = PortfolioAnalyticsEngine()
    report = engine.compute_analytics(result, context=ctx)

    assert report.backtest_id == "bt-full-run-h"
    assert report.performance.total_return == 0.10
    assert report.context.risk_free_rate == 0.02
    assert isinstance(report, AnalyticsReport)


def test_analytics_models_immutability_and_validation():
    perf = PerformanceMetrics(total_return=0.10, cagr=0.10, annualized_return=0.10, volatility=0.05)
    with pytest.raises(ValidationError):
        perf.total_return = 0.20

    sym = SymbolPerformance(symbol="BTC/USDT", net_pnl=100.0)
    with pytest.raises(ValidationError):
        sym.net_pnl = 200.0


def test_single_snapshot_edge_case():
    snapshots = create_sample_snapshots([100000.0])
    eq_analysis = EquityCurveEngine.calculate(snapshots)
    perf = PerformanceMetricsEngine.calculate(snapshots, eq_analysis.daily_returns)
    drawdown = DrawdownEngine.calculate(snapshots)

    assert eq_analysis.daily_returns == []
    assert perf.volatility == 0.0
    assert drawdown.max_drawdown == 0.0
