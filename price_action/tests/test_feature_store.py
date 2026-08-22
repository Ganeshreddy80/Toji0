"""Unit tests for PriceActionFeatureStore."""

from __future__ import annotations

from datetime import datetime, timezone

from price_action.core.enums import MarketRegimeType, TrendDirection
from price_action.core.feature_store import PriceActionFeatureStore
from price_action.core.models import (
    MarketRegimeState,
    MultiTimeframePriceActionSnapshot,
    TimeframePriceActionSnapshot,
    TrendMetrics,
)


def test_feature_store_crud_and_thread_safety():
    store = PriceActionFeatureStore()
    now = datetime.now(timezone.utc)

    tf_snap = TimeframePriceActionSnapshot(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=now,
        trend=TrendMetrics(direction=TrendDirection.BULLISH, strength=0.75),
        regime=MarketRegimeState(regime=MarketRegimeType.TRENDING_BULLISH),
    )

    mtf_snap = MultiTimeframePriceActionSnapshot(
        symbol="BTC/USDT",
        timestamp=now,
        timeframe_snapshots={"1h": tf_snap},
        primary_regime=MarketRegimeType.TRENDING_BULLISH,
        primary_trend=TrendDirection.BULLISH,
        confluence_score=85.0,
    )

    store.store_snapshot(mtf_snap)

    latest = store.get_latest_snapshot("BTC/USDT")
    assert latest is not None
    assert latest.symbol == "BTC/USDT"
    assert latest.confluence_score == 85.0

    features = store.get_features("BTC/USDT", "1h")
    assert features is not None
    assert features.features["trend_direction"] == "BULLISH"
    assert features.features["primary_regime"] == "TRENDING_BULLISH"

    store.clear()
    assert store.get_latest_snapshot("BTC/USDT") is None
