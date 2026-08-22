"""Unit tests for the Market Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from data.feature_store import FeatureCache, FeatureRegistry
from data.providers.implementations import BinanceProvider
from orchestrators.market_orchestrator.market import MarketOrchestrator
from toji_platform.core.event_bus import InMemoryEventBus


def test_market_orchestrator_pipeline() -> None:
    """Verify that MarketOrchestrator validates, computes features, and publishes data."""
    bus = InMemoryEventBus()
    provider = BinanceProvider()
    cache = FeatureCache()
    registry = FeatureRegistry()

    # Register mock feature definition
    mock_df = pd.DataFrame({"close": [95200.0], "volume": [10.0], "ema": [95000.0]})
    mock_feature = MagicMock()
    mock_feature.name = "EMA"
    mock_feature.version = "1.0.0"
    mock_feature.calculate.return_value = mock_df
    registry.register(mock_feature)

    orch = MarketOrchestrator(
        event_bus=bus,
        provider=provider,
        feature_cache=cache,
        feature_registry=registry,
    )

    events = []
    bus.subscribe("system.market_data_updated", events.append)

    start = datetime(2026, 6, 25, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 25, 1, 0, tzinfo=timezone.utc)

    orch.process_market_data("BTC/USDT", "1m", start, end)

    assert len(events) == 1
    assert events[0].payload["symbol"] == "BTC/USDT"
    assert "EMA" in events[0].payload["features"]
