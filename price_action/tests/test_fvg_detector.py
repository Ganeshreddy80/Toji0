"""Unit tests for FairValueGapDetector."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.fvg_detector import FairValueGapDetector
from price_action.core.enums import PatternDirection
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_fvg_detector_bullish_gap():
    detector = FairValueGapDetector()
    now = datetime.now(timezone.utc)

    # Candle 1 high: 100.0, Candle 2 (large up), Candle 3 low: 102.0 -> Gap (100.0 to 102.0)
    bars = [
        PriceActionBar(timestamp=now, open=98.0, high=100.0, low=97.0, close=99.0, index=0),
        PriceActionBar(timestamp=now, open=99.0, high=105.0, low=99.0, close=104.0, index=1),
        PriceActionBar(timestamp=now, open=104.0, high=108.0, low=102.0, close=107.0, index=2),
    ]

    cfg = PriceActionConfig(fvg_min_gap_pct=0.001)
    fvgs = detector.detect_fvgs(bars, cfg)

    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.direction == PatternDirection.BULLISH
    assert fvg.bottom == 100.0
    assert fvg.top == 102.0
    assert fvg.midpoint == 101.0
    assert fvg.is_mitigated is False


def test_fvg_detector_empty():
    detector = FairValueGapDetector()
    assert detector.detect_fvgs([]) == []
