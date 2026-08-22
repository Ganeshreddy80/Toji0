"""Unit tests for MarketStructureDetector."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.market_structure_detector import MarketStructureDetector
from price_action.core.enums import MarketStructureType, SwingType, TrendDirection
from price_action.core.models import PriceActionBar, PriceActionSwing


def test_market_structure_bullish_bos():
    detector = MarketStructureDetector()
    now = datetime.now(timezone.utc)

    swings = [
        PriceActionSwing(swing_type=SwingType.SWING_HIGH, price=100.0, timestamp=now, index=2),
        PriceActionSwing(swing_type=SwingType.SWING_LOW, price=90.0, timestamp=now, index=4),
        PriceActionSwing(swing_type=SwingType.SWING_HIGH, price=110.0, timestamp=now, index=6),
        PriceActionSwing(swing_type=SwingType.SWING_LOW, price=95.0, timestamp=now, index=8),
    ]

    bars = [PriceActionBar(timestamp=now, open=100.0, high=112.0, low=99.0, close=111.0, index=9)]
    state = detector.detect_market_structure(bars, swings)

    assert state.trend_bias == TrendDirection.BULLISH
    assert state.last_structure_type == MarketStructureType.BOS
    assert state.last_bos_price == 110.0


def test_market_structure_empty():
    detector = MarketStructureDetector()
    state = detector.detect_market_structure([], [])
    assert state.trend_bias == TrendDirection.SIDEWAYS
    assert state.last_structure_type is None
