"""Unit tests for the Institutional Feature Platform.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.feature_platform.cache import FeatureCache
from research_platform.feature_platform.dependency_graph import DependencyGraph
from research_platform.feature_platform.events import FeatureRegistered
from research_platform.feature_platform.models import FeatureRecord
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from research_platform.feature_platform.validators import FeatureValidator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return FeaturePlatformOrchestrator(event_bus)


def test_feature_registry_and_dependency_checks(orchestrator):
    """Verify registry saves definitions and validates dependency lists."""
    close_rec = FeatureRecord(
        uuid=str(uuid.uuid4()),
        name="close",
        display_name="Close Price",
        description="Close price series",
        formula="close",
        category="Price",
        subcategory="Raw",
        owner="quants",
        author="CTO",
        version="1.0.0",
        update_frequency="1m",
        warmup_length=0,
        lookback_window=0,
        required_resolution="1m"
    )
    log_ret_rec = FeatureRecord(
        uuid=str(uuid.uuid4()),
        name="log_return",
        display_name="Log Return",
        description="Log returns of close price",
        formula="log(close/close_prev)",
        category="Returns",
        subcategory="Transforms",
        owner="quants",
        author="CTO",
        version="1.0.0",
        dependencies=["close"],  # depends on close
        update_frequency="1m",
        warmup_length=1,
        lookback_window=1,
        required_resolution="1m"
    )

    orchestrator.register_feature(close_rec)
    orchestrator.register_feature(log_ret_rec)

    assert orchestrator.registry.get("close") is not None
    assert orchestrator.registry.get("log_return") is not None
    assert len(orchestrator.registry.list_all()) == 2

    # Reject duplicate registrations
    with pytest.raises(ValueError):
        orchestrator.registry.register(close_rec)

    # Reject registration if dependency is missing
    missing_dep_rec = FeatureRecord(
        uuid=str(uuid.uuid4()),
        name="volatility",
        display_name="Volatility",
        description="Volatility",
        formula="std(returns)",
        category="Risk",
        subcategory="Stats",
        owner="quants",
        author="CTO",
        version="1.0.0",
        dependencies=["missing_feature"],  # doesn't exist
        update_frequency="1m",
        warmup_length=10,
        lookback_window=10,
        required_resolution="1m"
    )
    with pytest.raises(ValueError):
        orchestrator.register_feature(missing_dep_rec)


def test_dependency_graph_cycle_detection():
    """Verify DAG detects circular dependency loops."""
    graph = DependencyGraph()
    graph.add_node("A", ["B"])
    graph.add_node("B", ["C"])
    graph.add_node("C", ["A"])  # Loop: A -> B -> C -> A

    assert graph.has_cycle() is True

    with pytest.raises(ValueError):
        graph.topological_sort()


def test_dependency_graph_sorting():
    """Verify linear topological execution order planning."""
    graph = DependencyGraph()
    graph.add_node("close", [])
    graph.add_node("log_return", ["close"])
    graph.add_node("rolling_std", ["log_return"])
    graph.add_node("atr", ["close"])
    graph.add_node("normalized_atr", ["atr", "close"])

    plan = graph.get_execution_plan(["rolling_std", "normalized_atr"])
    
    # Must compute dependencies first
    assert plan.index("close") < plan.index("log_return")
    assert plan.index("log_return") < plan.index("rolling_std")
    assert plan.index("close") < plan.index("atr")
    assert plan.index("atr") < plan.index("normalized_atr")

    # Reverse dependencies
    revs = graph.get_reverse_dependencies("close")
    assert set(revs) == {"log_return", "rolling_std", "atr", "normalized_atr"}


def test_pipeline_calculations(orchestrator):
    """Verify sequential computation of nested indicators Close -> LogReturn -> RollingStd -> ATR."""
    # Pre-register elements
    orchestrator.register_feature(FeatureRecord(uuid="1", name="close", display_name="Close", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", update_frequency="1m", warmup_length=0, lookback_window=0, required_resolution="1m"))
    orchestrator.register_feature(FeatureRecord(uuid="2", name="log_return", display_name="Returns", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=1, lookback_window=1, required_resolution="1m"))
    orchestrator.register_feature(FeatureRecord(uuid="3", name="rolling_std", display_name="Std", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", dependencies=["log_return"], update_frequency="1m", warmup_length=2, lookback_window=20, required_resolution="1m"))
    orchestrator.register_feature(FeatureRecord(uuid="4", name="atr", display_name="ATR", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"))
    orchestrator.register_feature(FeatureRecord(uuid="5", name="normalized_atr", display_name="NATR", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", dependencies=["atr", "close"], update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"))
    orchestrator.register_feature(FeatureRecord(uuid="6", name="risk_score", display_name="Risk", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", dependencies=["normalized_atr"], update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"))
    orchestrator.register_feature(FeatureRecord(uuid="7", name="signal", display_name="Signal", description="", formula="", category="", subcategory="", owner="", author="", version="1.0.0", dependencies=["risk_score"], update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"))

    # Mock historical ticks input (50 rows)
    times = pd.date_range("2026-06-25 12:00:00", periods=60, freq="1min")
    input_df = pd.DataFrame({
        "timestamp": times,
        "close": [100.0 + i * 0.1 for i in range(60)],
        "high": [102.0 + i * 0.1 for i in range(60)],
        "low": [98.0 + i * 0.1 for i in range(60)],
        "symbol": "BTC/USDT"
    })

    # Compute and persist
    output_df = orchestrator.compute_and_store(["signal", "rolling_std"], "BTC/USDT", input_df)

    assert "log_return" in output_df.columns
    assert "rolling_std" in output_df.columns
    assert "atr" in output_df.columns
    assert "normalized_atr" in output_df.columns
    assert "risk_score" in output_df.columns
    assert "signal" in output_df.columns


def test_feature_validator():
    """Verify validator flags lookahead bias, missing ratios, and stationarity."""
    validator = FeatureValidator()

    # Case 1: Healthy stationary dataset
    df_clean = pd.DataFrame({
        "timestamp": pd.date_range("2026-06-25 12:00:00", periods=100, freq="1min"),
        "my_feature": np.random.normal(loc=0.0, scale=1.0, size=100),
        "close": [100.0] * 100
    })

    res = validator.validate("my_feature", df_clean)
    assert res.is_approved is True
    assert res.nan_ratio == 0.0
    assert res.infinite_values_count == 0
    assert res.has_lookahead_bias is False

    # Case 2: lookahead bias (non-monotonic timestamps)
    df_leak = pd.DataFrame({
        "timestamp": list(reversed(pd.date_range("2026-06-25 12:00:00", periods=10, freq="1min"))),
        "my_feature": np.random.normal(loc=0.0, scale=1.0, size=10),
        "close": [100.0] * 10
    })
    res_leak = validator.validate("my_feature", df_leak)
    assert res_leak.is_approved is False
    assert res_leak.has_lookahead_bias is True


def test_feature_cache():
    """Verify hash-based cache key lookups, sets, and clears."""
    cache = FeatureCache()
    key = cache.generate_key("RSI", "1.0.0", "BTC/USDT", {"period": 14})
    
    df = pd.DataFrame({"rsi": [50.0, 52.0]})
    cache.set(key, df)

    loaded = cache.get(key)
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded.iloc[1]["rsi"] == 52.0

    cache.clear()
    assert cache.get(key) is None
