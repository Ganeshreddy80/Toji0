"""Unit tests for TrendEngine."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.trend_engine import TrendEngine
from price_action.core.enums import TrendDirection
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_trend_engine_bullish_alignment():
    engine = TrendEngine()
    now = datetime.now(timezone.utc)

    # 30 uptrending bars
    bars = [
        PriceActionBar(timestamp=now, open=100.0 + i, high=102.0 + i, low=99.0 + i, close=101.0 + i, index=i)
        for i in range(30)
    ]

    cfg = PriceActionConfig(fast_ma_period=5, slow_ma_period=20)
    metrics = engine.analyze_trend(bars, cfg)

    assert metrics.direction == TrendDirection.BULLISH
    assert metrics.fast_ma > metrics.slow_ma
    assert metrics.is_aligned is True
    assert metrics.strength > 0.0


def test_trend_engine_empty():
    engine = TrendEngine()
    metrics = engine.analyze_trend([])
    assert metrics.direction == TrendDirection.SIDEWAYS
    assert metrics.strength == 0.0
