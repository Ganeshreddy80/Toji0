"""FP-1 Feature Registration Lifecycle Tests.

Proves:
1. FeaturePlatformPlugin initialization registers all 20 canonical features.
2. register_default_features() is idempotent.
3. Runtime tick computation operates without per-tick register_feature calls.
4. Spying on register_feature verifies 0 calls occur during tick processing.
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pandas as pd
import pytest

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus, IEventBus

from research_platform.feature_platform.orchestrator import (
    DEFAULT_FEATURE_DEFINITIONS,
    FeaturePlatformOrchestrator
)
from research_platform.feature_platform.plugin import FeaturePlatformPlugin


@pytest.fixture
def container_with_plugin():
    container = Container()
    event_bus = InMemoryEventBus()
    container.register(IEventBus, instance=event_bus)
    plugin = FeaturePlatformPlugin(container)
    plugin.initialize()
    return container


def test_plugin_initialization_registers_all_canonical_features(container_with_plugin):
    """Verify FeaturePlatformPlugin.initialize() registers all 21 default production features."""
    orchestrator = container_with_plugin.resolve(FeaturePlatformOrchestrator)
    all_features = orchestrator.registry.list_all()
    assert len(all_features) == 21

    registered_names = {f.name for f in all_features}
    expected_names = {f.name for f in DEFAULT_FEATURE_DEFINITIONS}
    assert registered_names == expected_names

    # Check key features present
    for name in ["open", "high", "low", "close", "volume", "ema9", "ema21", "ema50", "rsi", "atr", "volume_change", "support", "resistance", "breakout", "trend", "risk_score", "signal", "annualized_vol"]:
        assert name in registered_names


def test_register_default_features_idempotency(container_with_plugin):
    """Verify calling register_default_features multiple times is safe and idempotent."""
    orchestrator = container_with_plugin.resolve(FeaturePlatformOrchestrator)
    assert len(orchestrator.registry.list_all()) == 21

    # Execute register_default_features again
    orchestrator.register_default_features()
    assert len(orchestrator.registry.list_all()) == 21


def test_runtime_tick_computation_without_per_tick_registration(container_with_plugin):
    """Verify compute_and_store executes cleanly during ticks without requiring register_feature."""
    orchestrator = container_with_plugin.resolve(FeaturePlatformOrchestrator)

    # Create dummy bars DataFrame
    df = pd.DataFrame([
        {"timestamp": 1000, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 500.0},
        {"timestamp": 2000, "open": 102.0, "high": 108.0, "low": 101.0, "close": 107.0, "volume": 700.0},
    ])

    features_to_compute = [
        "open", "high", "low", "close", "ema9", "ema21", "ema50",
        "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
    ]

    # Spy on register_feature method
    orchestrator.register_feature = MagicMock(side_effect=orchestrator.register_feature)

    # Execute tick computation
    output_df = orchestrator.compute_and_store(features_to_compute, "BTCUSDT", df)

    # Verify output
    assert not output_df.empty
    for feat in features_to_compute:
        assert feat in output_df.columns

    # Verify ZERO calls to register_feature occurred during tick computation
    assert orchestrator.register_feature.call_count == 0
