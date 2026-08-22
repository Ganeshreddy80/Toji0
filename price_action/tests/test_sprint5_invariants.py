"""Unit tests verifying all 10 Sprint 5 Architectural Invariants for the Price Action Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from price_action.analysis.fvg_detector import FairValueGapDetector
from price_action.analysis.liquidity_engine import LiquidityEngine
from price_action.analysis.market_regime_engine import MarketRegimeEngine
from price_action.analysis.market_structure_detector import MarketStructureDetector
from price_action.analysis.momentum_engine import MomentumEngine
from price_action.analysis.multi_timeframe_aggregator import MultiTimeframeAggregator
from price_action.analysis.order_block_detector import OrderBlockDetector
from price_action.analysis.premium_discount_engine import PremiumDiscountEngine
from price_action.analysis.swing_detector import SwingDetector
from price_action.analysis.trend_engine import TrendEngine
from price_action.analysis.volatility_engine import VolatilityEngine
from price_action.core import models as mod_models
from price_action.core.models import (
    MultiTimeframePriceActionSnapshot,
    PriceActionBar,
    PriceActionConfig,
    PriceActionFeatures,
    PriceActionSwing,
    TimeframePriceActionSnapshot,
)
from price_action.core.orchestrator import PriceActionOrchestrator


# =============================================================================
# Invariant 1 & 2: Never Generate BUY/SELL Decisions & Never Submit Orders
# =============================================================================

def test_invariant_never_generate_decisions_or_submit_orders():
    """Verify that Price Action models have zero order, position, broker, or decision fields."""
    for model_cls in (
        TimeframePriceActionSnapshot,
        MultiTimeframePriceActionSnapshot,
        PriceActionFeatures,
    ):
        fields = set(model_cls.model_fields.keys())
        forbidden = {"buy", "sell", "decision", "submit_order", "execute_order", "broker", "order_id"}
        assert fields.isdisjoint(forbidden), f"{model_cls.__name__} contains forbidden decision/order fields"


# =============================================================================
# Invariant 3: Never Perform Position Sizing
# =============================================================================

def test_invariant_never_perform_position_sizing():
    """Verify that Price Action models contain zero position sizing or risk allocation fields."""
    for model_cls in (
        TimeframePriceActionSnapshot,
        MultiTimeframePriceActionSnapshot,
        PriceActionFeatures,
    ):
        fields = set(model_cls.model_fields.keys())
        forbidden = {"quantity", "lots", "leverage", "position_size", "margin_required"}
        assert fields.isdisjoint(forbidden), f"{model_cls.__name__} contains forbidden sizing fields"


# =============================================================================
# Invariant 4: Never Bypass the Strategy Engine
# =============================================================================

def test_invariant_never_bypass_strategy_engine():
    """Verify that orchestrator outputs are stored in FeatureStore / published to EventBus for Strategy consumption."""
    orch = PriceActionOrchestrator()
    orch.initialize()

    now = datetime.now(timezone.utc)
    bars = [PriceActionBar(timestamp=now, open=100.0, high=101.0, low=99.0, close=100.5, index=i) for i in range(10)]

    mtf = orch.process_multi_timeframe("BTC/USDT", {"1h": bars})
    feat = orch.feature_store.get_features("BTC/USDT", "1h")

    assert feat is not None
    assert "primary_regime" in feat.features
    assert "trend_direction" in feat.features


# =============================================================================
# Invariant 5: Never Modify Historical Market Data
# =============================================================================

def test_invariant_never_modify_historical_market_data():
    """Verify input candles are frozen and unmodifiable."""
    now = datetime.now(timezone.utc)
    bar = PriceActionBar(timestamp=now, open=100.0, high=105.0, low=95.0, close=102.0, index=0)

    with pytest.raises(Exception):
        bar.close = 200.0


# =============================================================================
# Invariant 6: Derived Features Must Be Immutable
# =============================================================================

def test_invariant_derived_features_immutable():
    """Verify TimeframePriceActionSnapshot and MultiTimeframePriceActionSnapshot are frozen."""
    snap = TimeframePriceActionSnapshot(symbol="BTC/USDT", timeframe="1h")

    with pytest.raises(Exception):
        snap.symbol = "ETH/USDT"


# =============================================================================
# Invariant 7: Identical Market Data Must Produce Identical Features
# =============================================================================

def test_invariant_deterministic_detection():
    """Verify identical bar inputs produce 100% identical price action feature outputs."""
    now = datetime.now(timezone.utc)
    bars = [PriceActionBar(timestamp=now, open=100.0 + i, high=102.0 + i, low=99.0 + i, close=101.0 + i, index=i) for i in range(20)]

    orch1 = PriceActionOrchestrator()
    orch1.initialize()
    snap1 = orch1.process_candles("BTC/USDT", "1h", bars)

    orch2 = PriceActionOrchestrator()
    orch2.initialize()
    snap2 = orch2.process_candles("BTC/USDT", "1h", bars)

    assert snap1.trend.direction == snap2.trend.direction
    assert snap1.volatility.atr == snap2.volatility.atr
    assert len(snap1.swings) == len(snap2.swings)


# =============================================================================
# Invariant 8: Invalid Market Data Must Fail Closed
# =============================================================================

def test_invariant_invalid_data_fails_closed():
    """Verify empty/corrupted data returns safe empty snapshot without raising exceptions."""
    orch = PriceActionOrchestrator()
    orch.initialize()

    snap = orch.process_candles("BTC/USDT", "1h", [])
    assert snap.symbol == "BTC/USDT"
    assert snap.trend.direction.value == "SIDEWAYS"


# =============================================================================
# Invariant 9: Detection Modules Must Remain Independent
# =============================================================================

def test_invariant_detectors_independent():
    """Verify detectors can be instantiated and executed independently."""
    now = datetime.now(timezone.utc)
    bars = [PriceActionBar(timestamp=now, open=100.0, high=101.0, low=99.0, close=100.0, index=i) for i in range(10)]

    swing_det = SwingDetector()
    swings = swing_det.detect_swings(bars)
    assert isinstance(swings, list)

    fvg_det = FairValueGapDetector()
    fvgs = fvg_det.detect_fvgs(bars)
    assert isinstance(fvgs, list)


# =============================================================================
# Invariant 10: All Thresholds and Detector Parameters Must Be Configurable
# =============================================================================

def test_invariant_parameters_configurable():
    """Verify PriceActionConfig parameters customizability across engines."""
    cfg = PriceActionConfig(
        swing_lookback=5,
        fast_ma_period=10,
        slow_ma_period=30,
        atr_period=20,
        rsi_period=10,
    )

    bars = [PriceActionBar(timestamp=datetime.now(timezone.utc), open=100.0, high=102.0, low=98.0, close=101.0, index=i) for i in range(35)]
    trend_eng = TrendEngine()
    metrics = trend_eng.analyze_trend(bars, cfg)

    assert metrics.fast_ma > 0.0
