"""Unit tests for MomentumEngine."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.momentum_engine import MomentumEngine
from price_action.core.enums import DivergenceType
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_momentum_engine_rsi_and_macd():
    engine = MomentumEngine()
    now = datetime.now(timezone.utc)

    # 35 bars
    bars = [
        PriceActionBar(timestamp=now, open=100.0 + (i * 0.5), high=102.0 + (i * 0.5), low=99.0 + (i * 0.5), close=101.0 + (i * 0.5), index=i)
        for i in range(35)
    ]

    cfg = PriceActionConfig(rsi_period=14, macd_fast=12, macd_slow=26, macd_signal=9)
    metrics = engine.analyze_momentum(bars, [], cfg)

    assert 0.0 <= metrics.rsi <= 100.0
    assert metrics.divergence == DivergenceType.NONE


def test_momentum_engine_empty():
    engine = MomentumEngine()
    metrics = engine.analyze_momentum([], [])
    assert metrics.rsi == 50.0
    assert metrics.macd == 0.0
