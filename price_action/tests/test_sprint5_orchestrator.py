"""Unit tests for Sprint 5 PriceActionOrchestrator pipeline execution."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from price_action.core.enums import MarketRegimeType, TrendDirection
from price_action.core.orchestrator import PriceActionOrchestrator
from price_action.core.models import PriceActionBar, PriceActionConfig


def test_orchestrator_process_candles():
    mock_event_bus = MagicMock()
    orch = PriceActionOrchestrator()
    orch.initialize(event_bus=mock_event_bus)

    now = datetime.now(timezone.utc)
    bars = [
        PriceActionBar(timestamp=now, open=100.0 + i, high=102.0 + i, low=99.0 + i, close=101.0 + i, volume=100.0, index=i)
        for i in range(25)
    ]

    tf_snap = orch.process_candles("BTC/USDT", "1h", bars)

    assert tf_snap.symbol == "BTC/USDT"
    assert tf_snap.timeframe == "1h"
    assert tf_snap.trend.direction == TrendDirection.BULLISH
    assert mock_event_bus.publish.called


def test_orchestrator_process_multi_timeframe():
    mock_event_bus = MagicMock()
    orch = PriceActionOrchestrator()
    orch.initialize(event_bus=mock_event_bus)

    now = datetime.now(timezone.utc)
    bars_1h = [
        PriceActionBar(timestamp=now, open=100.0 + i, high=102.0 + i, low=99.0 + i, close=101.0 + i, volume=100.0, index=i)
        for i in range(25)
    ]
    bars_4h = [
        PriceActionBar(timestamp=now, open=100.0 + i, high=103.0 + i, low=98.0 + i, close=102.0 + i, volume=400.0, index=i)
        for i in range(25)
    ]

    mtf_dict = {"1h": bars_1h, "4h": bars_4h}
    mtf_snap = orch.process_multi_timeframe("BTC/USDT", mtf_dict)

    assert mtf_snap.symbol == "BTC/USDT"
    assert "1h" in mtf_snap.timeframe_snapshots
    assert "4h" in mtf_snap.timeframe_snapshots
    assert mtf_snap.confluence_score > 0.0

    # Feature Store integration test
    features = orch.feature_store.get_features("BTC/USDT", "1h")
    assert features is not None
    assert features.features["symbol"] == "BTC/USDT"


def test_orchestrator_fails_closed_on_invalid_data():
    mock_event_bus = MagicMock()
    orch = PriceActionOrchestrator()
    orch.initialize(event_bus=mock_event_bus)

    # Empty bar list fails closed gracefully returning empty snapshot without raising
    tf_snap = orch.process_candles("BTC/USDT", "1h", [])
    assert tf_snap.symbol == "BTC/USDT"
    assert len(tf_snap.swings) == 0
