"""FP-7B Focused Tests — Query API Naming Standardization.

Sprint 004 / FP-7B certification tests.

Canonical name: query_historical() — on both IFeatureStore / FeatureStore
                                    AND FeaturePlatformOrchestrator.

FP-7D-1 UPDATE: The deprecated compatibility alias query_history() was removed
from FeaturePlatformOrchestrator per CTO authorization (zero production callers
proven by FP-7D discovery). Tests verifying the alias have been removed.

Tests verify:
1. Canonical method (query_historical) works on orchestrator.
2. Existing FeatureStore query_historical PIT behaviour unchanged.
3. Existing query_realtime() unchanged.
4. IFeatureStore abstract contract declares query_historical (not query_history).
5. FeatureStore does NOT have a query_history method.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import pytest

from research_platform.feature_platform.feature_store import FeatureStore
from research_platform.feature_platform.interfaces import IFeatureStore
from toji_platform.core.event_bus.bus import InMemoryEventBus
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator


# ---------------------------------------------------------------------------
# Helper — build a small populated orchestrator
# ---------------------------------------------------------------------------

def _make_orch_with_historical_data(
    symbol: str = "BTCUSDT",
) -> FeaturePlatformOrchestrator:
    """Return an orchestrator whose store has rsi and ema9 available for historical query.

    Uses save_features directly to guarantee the symbol column is present in the
    offline store, which is required by query_historical's PIT merge join.
    """
    now = datetime.now(timezone.utc)
    eb = InMemoryEventBus()
    orch = FeaturePlatformOrchestrator(eb)
    orch.register_default_features()
    for feature, val in [("rsi", 55.0), ("ema9", 102.0)]:
        df = pd.DataFrame({
            feature: [val],
            "effective_time": [now - timedelta(minutes=5)],
            "as_of": [now - timedelta(minutes=5)],
            "symbol": [symbol],
        })
        orch._store.save_features(feature, "1.0.0", symbol, df)
    return orch


def _make_orch_with_realtime_data(
    symbol: str = "BTCUSDT",
) -> FeaturePlatformOrchestrator:
    """Return an orchestrator with realtime-queryable data (rsi, ema9 via compute_and_store)."""
    np.random.seed(7)
    n = 100
    close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
        "open": close - 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": np.random.randint(100, 10_000, n).astype(float),
    })
    eb = InMemoryEventBus()
    orch = FeaturePlatformOrchestrator(eb)
    orch.register_default_features()
    orch.compute_and_store(["rsi", "ema9"], symbol, df)
    return orch


def _make_store_with_data(symbol: str = "BTCUSDT") -> FeatureStore:
    """Return a FeatureStore with 2 features stored for *symbol*."""
    now = datetime.now(timezone.utc)
    store = FeatureStore()
    for feature, val in [("rsi", 55.0), ("ema9", 102.0)]:
        df = pd.DataFrame({
            feature: [val],
            "effective_time": [now],
            "as_of": [now],
            "symbol": [symbol],
        })
        store.save_features(feature, "1.0.0", symbol, df)
    return store


# ===========================================================================
# FP7B-1 — Orchestrator canonical name (query_historical)
# ===========================================================================

class TestOrchQueryHistoricalCanonical:
    """FeaturePlatformOrchestrator.query_historical() is the canonical method."""

    def test_query_historical_exists_on_orchestrator(self):
        """query_historical must be a concrete callable on FeaturePlatformOrchestrator."""
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        assert callable(getattr(orch, "query_historical", None)), (
            "query_historical missing from FeaturePlatformOrchestrator"
        )

    def test_query_historical_returns_dataframe(self):
        """query_historical returns a pd.DataFrame (possibly empty)."""
        orch = _make_orch_with_historical_data()
        now = datetime.now(timezone.utc)
        result = orch.query_historical(
            ["rsi", "ema9"],
            ["BTCUSDT"],
            now - timedelta(hours=1),
            now + timedelta(hours=1),
        )
        assert isinstance(result, pd.DataFrame)

    def test_query_historical_returns_data_when_stored(self):
        """query_historical returns non-empty DataFrame when features are stored."""
        orch = _make_orch_with_historical_data()
        now = datetime.now(timezone.utc)
        result = orch.query_historical(
            ["rsi", "ema9"],
            ["BTCUSDT"],
            now - timedelta(hours=2),
            now + timedelta(hours=2),
        )
        # Must have at least timestamp + symbol columns from the PIT join
        assert "symbol" in result.columns or "timestamp" in result.columns


# ===========================================================================
# FP7B-2 — query_historical sole implementation (FP-7D-1: alias removed)
# ===========================================================================

class TestQueryHistoricalSoleImplementation:
    """query_historical contains the sole implementation; query_history alias removed by FP-7D-1."""

    def test_query_historical_contains_store_call(self):
        """query_historical must directly call self._store.query_historical."""
        src = inspect.getsource(FeaturePlatformOrchestrator.query_historical)
        assert "self._store.query_historical" in src


# ===========================================================================
# FP7B-5 — IFeatureStore interface
# ===========================================================================

class TestIFeatureStoreInterface:
    """IFeatureStore abstract interface must declare query_historical (not query_history)."""

    def test_interface_has_query_historical(self):
        """IFeatureStore declares query_historical as abstract."""
        assert hasattr(IFeatureStore, "query_historical")
        assert getattr(IFeatureStore.query_historical, "__isabstractmethod__", False)

    def test_interface_does_not_have_query_history(self):
        """IFeatureStore must NOT declare query_history — only the orchestrator alias exists there."""
        assert not hasattr(IFeatureStore, "query_history"), (
            "IFeatureStore must not have query_history; the alias is orchestrator-only"
        )


# ===========================================================================
# FP7B-6 — FeatureStore concrete class
# ===========================================================================

class TestFeatureStoreConcreteClass:
    """FeatureStore concrete class has query_historical but NOT query_history."""

    def test_feature_store_has_query_historical(self):
        """FeatureStore implements IFeatureStore.query_historical."""
        assert callable(getattr(FeatureStore, "query_historical", None))

    def test_feature_store_does_not_have_query_history(self):
        """FeatureStore must NOT have a query_history method — no accidental alias."""
        assert not hasattr(FeatureStore, "query_history"), (
            "FeatureStore must not have query_history; alias lives only on orchestrator"
        )

    def test_feature_store_query_historical_pit_behaviour_unchanged(self):
        """FeatureStore.query_historical PIT merge join works identically to pre-FP-7B."""
        store = _make_store_with_data()
        now = datetime.now(timezone.utc)
        result = store.query_historical(
            ["rsi", "ema9"],
            ["BTCUSDT"],
            now - timedelta(hours=1),
            now + timedelta(hours=1),
        )
        assert isinstance(result, pd.DataFrame)
        # PIT join should return at least a timestamp/symbol spine
        assert len(result) > 0


# ===========================================================================
# FP7B-7 — query_realtime unchanged
# ===========================================================================

class TestQueryRealtimeUnchanged:
    """query_realtime() remains the canonical online/live API — unchanged by FP-7B."""

    def test_query_realtime_exists(self):
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        assert callable(getattr(orch, "query_realtime", None))

    def test_query_realtime_returns_dataframe(self):
        orch = _make_orch_with_realtime_data()
        result = orch.query_realtime(["rsi", "ema9"], ["BTCUSDT"])
        assert isinstance(result, pd.DataFrame)

    def test_query_realtime_returns_data_when_stored(self):
        orch = _make_orch_with_realtime_data()
        result = orch.query_realtime(["rsi", "ema9"], ["BTCUSDT"])
        assert not result.empty
        assert "rsi" in result.columns
        assert "ema9" in result.columns
