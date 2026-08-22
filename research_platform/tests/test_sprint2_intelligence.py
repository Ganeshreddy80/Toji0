"""Sprint 2 Trading Intelligence Engine comprehensive verification test suite with 250+ parameterized test check points."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

# Import Sprint 2 components
from research_platform.price_action.models import SwingPoint, MarketStructureChange, BlockStructure, ImbalanceGap
from research_platform.price_action.repository import PriceActionRepository
from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.multi_timeframe.top_down_analysis import TopDownAnalysisEngine
from research_platform.confluence.scoring_engine import ConfluenceScoringEngine
from research_platform.ai_signal.signal_generator import AISignalGenerator
from research_platform.strategy_framework.composer import StrategyComposer
from research_platform.strategy_framework.loader import StrategyLoader
from research_platform.strategy_framework.registry import StrategyFrameworkRegistry
from research_platform.risk_engine_v2.kelly_criterion import KellySizingEngine
from research_platform.risk_engine_v2.exposure_manager import PortfolioExposureManager
from research_platform.risk_engine_v2.circuit_breaker import CircuitBreaker
from research_platform.portfolio_intelligence.risk_parity import RiskParityAllocator
from research_platform.portfolio_intelligence.metrics import PortfolioMetricsCalculator
from research_platform.portfolio_intelligence.rebalancer import PortfolioRebalancer
from research_platform.research_intelligence.validation import WalkForwardValidator, MonteCarloSimulator
from research_platform.research_intelligence.feature_ranking import FeatureAndModelRanker


@pytest.fixture
def mock_container():
    container = MagicMock()
    
    # Setup mock event bus
    event_bus = MagicMock()
    container.resolve.side_effect = lambda t: {
        "IEventBus": event_bus,
        "PriceActionOrchestrator": container.pa_orch,
        "TopDownAnalysisEngine": container.td_engine,
        "ConfluenceScoringEngine": container.confluence_engine,
    }.get(t if isinstance(t, str) else t.__name__)
    
    return container


# ── Phase 1: Price Action tests ───────────────────────────────────────────

def test_price_action_swings_and_indicators(mock_container):
    repo = PriceActionRepository()
    orch = PriceActionOrchestrator(event_bus=mock_container.resolve("IEventBus"), repository=repo)
    mock_container.pa_orch = orch

    symbol = "BTCUSDT"
    base_time = datetime.now(timezone.utc)

    # Process ticks to construct bars and verify VWAP calculations
    for i in range(1, 100):
        price = 50000.0 + (i % 5) * 10.0
        orch.process_tick(symbol, price, base_time + timedelta(seconds=i), volume=10.0)

    assert orch.get_vwap(symbol) > 0.0
    assert len(orch.get_bars(symbol)) > 0

    # Add manual swings to repository and assert retrievals
    swing_high = SwingPoint(point_type="HIGH", price=51000.0, timestamp=base_time, index=10)
    swing_low = SwingPoint(point_type="LOW", price=49000.0, timestamp=base_time, index=12)
    repo.save_swing(symbol, swing_high)
    repo.save_swing(symbol, swing_low)

    retrieved_swings = orch.get_swings(symbol)
    assert len(retrieved_swings) == 2
    assert retrieved_swings[0].point_type == "HIGH"
    assert retrieved_swings[1].point_type == "LOW"


def test_price_action_fvg_imbalances(mock_container):
    repo = PriceActionRepository()
    orch = PriceActionOrchestrator(event_bus=mock_container.resolve("IEventBus"), repository=repo)
    
    symbol = "ETHUSDT"
    base_time = datetime.now(timezone.utc)

    # Feed tick data across 5 minutes to form bars naturally with FVG pattern
    # Bar 0: high 3050, low 2990
    orch.process_tick(symbol, 3000.0, base_time, volume=100.0)
    orch.process_tick(symbol, 3050.0, base_time + timedelta(seconds=15), volume=0.0)
    orch.process_tick(symbol, 2990.0, base_time + timedelta(seconds=30), volume=0.0)
    orch.process_tick(symbol, 3040.0, base_time + timedelta(seconds=45), volume=0.0)

    # Bar 1: high 3100, low 3030
    t1 = base_time + timedelta(minutes=1)
    orch.process_tick(symbol, 3040.0, t1, volume=100.0)
    orch.process_tick(symbol, 3100.0, t1 + timedelta(seconds=15), volume=0.0)
    orch.process_tick(symbol, 3030.0, t1 + timedelta(seconds=30), volume=0.0)
    orch.process_tick(symbol, 3090.0, t1 + timedelta(seconds=45), volume=0.0)

    # Bar 2: high 3150, low 3110 (b3 low 3110 > b1 high 3050 -> Bullish FVG)
    t2 = base_time + timedelta(minutes=2)
    orch.process_tick(symbol, 3090.0, t2, volume=100.0)
    orch.process_tick(symbol, 3150.0, t2 + timedelta(seconds=15), volume=0.0)
    orch.process_tick(symbol, 3110.0, t2 + timedelta(seconds=30), volume=0.0)
    orch.process_tick(symbol, 3140.0, t2 + timedelta(seconds=45), volume=0.0)

    # Bar 3 & Bar 4 to meet 5-bar detector minimum
    t3 = base_time + timedelta(minutes=3)
    orch.process_tick(symbol, 3140.0, t3, volume=100.0)
    orch.process_tick(symbol, 3200.0, t3 + timedelta(seconds=15), volume=0.0)
    orch.process_tick(symbol, 3180.0, t3 + timedelta(seconds=30), volume=0.0)
    orch.process_tick(symbol, 3190.0, t3 + timedelta(seconds=45), volume=0.0)

    t4 = base_time + timedelta(minutes=4)
    orch.process_tick(symbol, 3190.0, t4, volume=100.0)
    orch.process_tick(symbol, 3250.0, t4 + timedelta(seconds=15), volume=0.0)
    orch.process_tick(symbol, 3230.0, t4 + timedelta(seconds=30), volume=0.0)
    orch.process_tick(symbol, 3240.0, t4 + timedelta(seconds=45), volume=0.0)

    # Bar 5 to trigger detectors for Bar 4 close
    t5 = base_time + timedelta(minutes=5)
    orch.process_tick(symbol, 3240.0, t5, volume=100.0)
    gaps = orch.get_gaps(symbol)
    assert len(gaps) > 0


# ── Phase 2: Multi-Timeframe tests ────────────────────────────────────────

def test_top_down_analysis(mock_container):
    repo = PriceActionRepository()
    orch = PriceActionOrchestrator(event_bus=mock_container.resolve("IEventBus"), repository=repo)
    mock_container.pa_orch = orch

    engine = TopDownAnalysisEngine(container=mock_container)
    mock_container.td_engine = engine

    res = engine.analyze_symbol("SOLUSDT")
    assert res.final_bias == "NEUTRAL"
    assert res.aligned is False


# ── Phase 3: Confluence Engine tests ──────────────────────────────────────

def test_confluence_scoring(mock_container):
    repo = PriceActionRepository()
    orch = PriceActionOrchestrator(event_bus=mock_container.resolve("IEventBus"), repository=repo)
    mock_container.pa_orch = orch

    td_engine = TopDownAnalysisEngine(container=mock_container)
    mock_container.td_engine = td_engine

    confluence_engine = ConfluenceScoringEngine(container=mock_container)
    mock_container.confluence_engine = confluence_engine

    res = confluence_engine.calculate_confluence("BTCUSDT", 50000.0)
    assert 0.0 <= res.score <= 100.0
    assert res.confidence in ["LOW", "MEDIUM", "HIGH"]
    assert res.strength in ["STRONG", "WEAK"]


# ── Phase 4: AI Signal Engine tests ───────────────────────────────────────

def test_ai_signal_generation(mock_container):
    repo = PriceActionRepository()
    orch = PriceActionOrchestrator(event_bus=mock_container.resolve("IEventBus"), repository=repo)
    mock_container.pa_orch = orch

    td_engine = TopDownAnalysisEngine(container=mock_container)
    mock_container.td_engine = td_engine

    confluence_engine = ConfluenceScoringEngine(container=mock_container)
    mock_container.confluence_engine = confluence_engine

    signal_gen = AISignalGenerator(container=mock_container)
    
    sig = signal_gen.generate_signal("BTCUSDT", 50000.0)
    assert sig.signal in ["BUY", "SELL", "WAIT"]
    assert sig.confidence >= 0.0
    assert sig.expected_win_rate >= 0.0


# ── Phase 5: Strategy Framework tests ─────────────────────────────────────

def test_strategy_composer_and_loader():
    composer = StrategyComposer()
    loader = StrategyLoader()

    types = [
        "TREND_FOLLOWING", "BREAKOUT", "MEAN_REVERSION", "MOMENTUM",
        "SCALPING", "SWING", "VOLATILITY", "GRID", "AI"
    ]
    
    for i, t in enumerate(types):
        strat = composer.compose(
            strategy_id=f"STRAT-{i}",
            name=f"Template {t}",
            strategy_type=t,
            version="1.0.0",
            symbols=["BTCUSDT"],
            parameters={"deviation": 2.0}
        )
        loader.load_strategy(strat)

    assert len(loader.get_all_active()) == 9

    updated_strat = composer.compose(
        strategy_id="STRAT-0",
        name="Template TREND_FOLLOWING",
        strategy_type="TREND_FOLLOWING",
        version="1.1.0",
        symbols=["BTCUSDT"],
        parameters={"deviation": 1.5}
    )
    loader.reload_strategy("STRAT-0", updated_strat)
    assert loader.get_strategy("STRAT-0").metadata.version == "1.1.0"


# ── Phase 6: Risk Engine V2 tests ─────────────────────────────────────────

# Parameterized test to run 300 test points for Kelly sizing logic
@pytest.mark.parametrize("win_rate, risk_reward, expected_sizing", [
    (wr / 100.0, rr, min(max(0.0, (wr / 100.0 - (1.0 - wr / 100.0) / rr) * 0.25), 0.10))
    for wr in range(20, 95, 3)  # 25 win-rates
    for rr in [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0]  # 12 payoff ratios -> 300 tests total
])
def test_kelly_sizing_matrix(win_rate, risk_reward, expected_sizing):
    kelly = KellySizingEngine(fraction_multiplier=0.25, max_fraction=0.10)
    size = kelly.calculate_sizing(win_rate, risk_reward)
    assert abs(size - expected_sizing) < 1e-5


# Parameterized test running 100 test points for Pearson correlations
@pytest.mark.parametrize("x_val, y_val", [
    (i * 0.1, i * 0.2) for i in range(1, 101)  # 100 tests total
])
def test_exposure_pearson_correlation(x_val, y_val):
    exposure = PortfolioExposureManager(sector_limits={"TECH": 0.40})
    # Seed prices
    for i in range(5):
        exposure.record_price("BTC", 50000.0 + i * x_val)
        exposure.record_price("ETH", 3000.0 + i * y_val)
    
    corr_res = exposure.calculate_correlation_matrix()
    assert corr_res["matrix"][0][1] > 0.99  # Perfectly correlated positive trend


def test_exposure_halts_and_circuit_breakers():
    # Exposure limit checks
    exposure = PortfolioExposureManager(sector_limits={"TECH": 0.40, "FIN": 0.30})
    exposure.update_exposure("TECH", 0.45)
    violations = exposure.check_sector_limits()
    assert len(violations) == 1

    # Circuit breakers test
    cb = CircuitBreaker()
    assert cb.is_trading_allowed("BTCUSDT") is True
    cb.halt_symbol("BTCUSDT", "Volatility shock spike")
    assert cb.is_trading_allowed("BTCUSDT") is False
    cb.trigger_global_kill_switch("Account drawdown limit breached")
    assert cb.is_trading_allowed("ETHUSDT") is False


# ── Phase 7: Portfolio Intelligence tests ─────────────────────────────────

def test_risk_parity_and_metrics():
    allocator = RiskParityAllocator()
    vols = {"BTC": 0.02, "ETH": 0.04, "SOL": 0.08}
    weights = allocator.calculate_weights(vols)
    
    # Assert inverse volatility distribution (BTC should have highest weight)
    assert weights["BTC"] > weights["ETH"] > weights["SOL"]
    assert abs(sum(weights.values()) - 1.0) < 1e-5

    # Metrics calculation
    calc = PortfolioMetricsCalculator()
    p_returns = [0.01, -0.005, 0.02, 0.015, -0.01]
    b_returns = [0.005, -0.002, 0.01, 0.008, -0.005]
    metrics = calc.calculate_ratios(p_returns, b_returns)
    assert metrics.sharpe_ratio is not None


# ── Phase 8: Research Intelligence tests ──────────────────────────────────

def test_validation_and_monte_carlo():
    val = WalkForwardValidator()
    splits = val.generate_splits(data_length=100, train_size=60, validation_size=20, step_size=10)
    assert len(splits) == 3

    mc = MonteCarloSimulator()
    hist_returns = [0.01, -0.02, 0.015, 0.005, -0.01]
    res = mc.run_simulations(hist_returns, n_simulations=100, horizon_days=10)
    assert "ruin_probability" in res
    assert "median_ending_value" in res
