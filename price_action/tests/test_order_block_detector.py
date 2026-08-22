"""Unit tests for OrderBlockDetector."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.order_block_detector import OrderBlockDetector
from price_action.core.enums import PatternDirection
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_order_block_detector_bullish():
    detector = OrderBlockDetector()
    now = datetime.now(timezone.utc)

    # c0: baseline, c1: bearish OB candle, c2: strong bullish expansion
    bars = [
        PriceActionBar(timestamp=now, open=100.0, high=101.0, low=99.0, close=100.0, volume=100.0, index=0),
        PriceActionBar(timestamp=now, open=100.0, high=100.5, low=97.0, close=97.5, volume=100.0, index=1),
        PriceActionBar(timestamp=now, open=97.5, high=108.0, low=97.5, close=107.0, volume=300.0, index=2),
    ]

    cfg = PriceActionConfig(ob_volume_surge_mult=1.1)
    obs = detector.detect_order_blocks(bars, [], cfg)

    assert len(obs) == 1
    ob = obs[0]
    assert ob.direction == PatternDirection.BULLISH
    assert ob.top == 100.5
    assert ob.bottom == 97.0


def test_order_block_detector_empty():
    detector = OrderBlockDetector()
    assert detector.detect_order_blocks([], []) == []
