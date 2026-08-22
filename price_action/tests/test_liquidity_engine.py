"""Unit tests for LiquidityEngine."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.liquidity_engine import LiquidityEngine
from price_action.core.enums import LiquidityType, SwingType
from price_action.core.models import PriceActionBar, PriceActionSwing


def test_liquidity_engine_bsl_and_ssl():
    engine = LiquidityEngine()
    now = datetime.now(timezone.utc)

    swings = [
        PriceActionSwing(swing_type=SwingType.SWING_HIGH, price=105.0, timestamp=now, index=2),
        PriceActionSwing(swing_type=SwingType.SWING_LOW, price=95.0, timestamp=now, index=4),
    ]

    bars = [PriceActionBar(timestamp=now, open=100.0, high=101.0, low=99.0, close=100.0, index=5)]

    pools = engine.detect_liquidity(bars, swings)
    assert len(pools) == 2

    types = [p.liquidity_type for p in pools]
    assert LiquidityType.BSL in types
    assert LiquidityType.SSL in types


def test_liquidity_engine_empty():
    engine = LiquidityEngine()
    assert engine.detect_liquidity([], []) == []
