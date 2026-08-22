"""Unit tests for SwingDetector."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.swing_detector import SwingDetector
from price_action.core.enums import SwingType
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_swing_detector_basic():
    detector = SwingDetector()
    now = datetime.now(timezone.utc)

    # 7 bars forming a pivot high at bar 3 (index 3, high 105.0) and pivot low at bar 5 (index 5, low 90.0)
    prices = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 102.0, 99.5, 101.0),
        (101.0, 103.0, 100.0, 102.0),
        (102.0, 106.0, 101.0, 105.0),  # Pivot High (106.0)
        (104.0, 104.5, 98.0, 99.0),
        (99.0, 99.5, 88.0, 89.0),     # Pivot Low (88.0)
        (89.0, 93.0, 88.5, 92.0),
    ]

    bars = [
        PriceActionBar(timestamp=now, open=o, high=h, low=l, close=c, index=i)
        for i, (o, h, l, c) in enumerate(prices)
    ]

    cfg = PriceActionConfig(swing_lookback=2)
    swings = detector.detect_swings(bars, cfg)

    assert len(swings) >= 1
    types = [s.swing_type for s in swings]
    assert SwingType.SWING_HIGH in types or SwingType.SWING_LOW in types


def test_swing_detector_empty():
    detector = SwingDetector()
    assert detector.detect_swings([]) == []
