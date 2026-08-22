"""Unit tests for VolatilityEngine."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.volatility_engine import VolatilityEngine
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_volatility_engine_calculation():
    engine = VolatilityEngine()
    now = datetime.now(timezone.utc)

    # 25 bars with constant volatility
    bars = [
        PriceActionBar(timestamp=now, open=100.0, high=105.0, low=95.0, close=100.0, index=i)
        for i in range(25)
    ]

    cfg = PriceActionConfig(atr_period=14, bb_period=20, bb_std_dev=2.0)
    metrics = engine.analyze_volatility(bars, cfg)

    assert metrics.atr > 0.0
    assert metrics.atr_percent > 0.0
    assert metrics.bb_upper >= metrics.bb_middle >= metrics.bb_lower
    assert metrics.bb_bandwidth >= 0.0


def test_volatility_engine_empty():
    engine = VolatilityEngine()
    metrics = engine.analyze_volatility([])
    assert metrics.atr == 0.0
    assert metrics.is_squeeze is False
