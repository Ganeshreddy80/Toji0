"""FP-7D-1 Focused Tests — query_history() Compatibility Alias Removal.

Sprint 004 / FP-7D-1 certification tests.

FP-7D discovery proved:
- ZERO production callers of query_history()
- ZERO external/public API callers
- query_historical() is the sole canonical API on FeaturePlatformOrchestrator

FP-7D-1 removed the deprecated compatibility alias.

Tests verify:
1. query_history is NOT present on FeaturePlatformOrchestrator.
2. query_history is NOT present on IFeatureStore.
3. query_history is NOT present on FeatureStore.
4. query_historical() remains present and functional on orchestrator.
5. query_realtime() remains present and functional on orchestrator.
6. FP-7C staleness parameter (max_age_seconds) remains intact.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from research_platform.feature_platform.interfaces import IFeatureStore
from research_platform.feature_platform.feature_store import FeatureStore
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from toji_platform.core.event_bus.bus import InMemoryEventBus


# ===========================================================================
# FP7D1-1 — query_history alias is gone
# ===========================================================================

class TestQueryHistoryAliasRemoved:
    """Verify query_history() has been fully removed from all Feature Platform classes."""

    def test_orchestrator_does_not_have_query_history(self):
        """FeaturePlatformOrchestrator must NOT have query_history after FP-7D-1."""
        assert not hasattr(FeaturePlatformOrchestrator, "query_history"), (
            "FP-7D-1 FAIL: query_history still exists on FeaturePlatformOrchestrator; "
            "it should have been removed"
        )

    def test_ifeaturestore_does_not_have_query_history(self):
        """IFeatureStore must NOT have query_history (unchanged — belt-and-suspenders)."""
        assert not hasattr(IFeatureStore, "query_history"), (
            "FP-7D-1 FAIL: query_history found on IFeatureStore"
        )

    def test_feature_store_does_not_have_query_history(self):
        """FeatureStore must NOT have query_history (unchanged — belt-and-suspenders)."""
        assert not hasattr(FeatureStore, "query_history"), (
            "FP-7D-1 FAIL: query_history found on FeatureStore"
        )

    def test_orchestrator_instance_does_not_have_query_history(self):
        """Instance-level check: no dynamic attachment of query_history."""
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        assert not hasattr(orch, "query_history"), (
            "FP-7D-1 FAIL: query_history accessible on orchestrator instance"
        )


# ===========================================================================
# FP7D1-2 — Canonical APIs remain intact
# ===========================================================================

class TestCanonicalAPIsPreserved:
    """Verify query_historical() and query_realtime() are unchanged."""

    def test_orchestrator_has_query_historical(self):
        """query_historical must remain on FeaturePlatformOrchestrator."""
        assert hasattr(FeaturePlatformOrchestrator, "query_historical")
        assert callable(FeaturePlatformOrchestrator.query_historical)

    def test_orchestrator_has_query_realtime(self):
        """query_realtime must remain on FeaturePlatformOrchestrator."""
        assert hasattr(FeaturePlatformOrchestrator, "query_realtime")
        assert callable(FeaturePlatformOrchestrator.query_realtime)

    def test_query_historical_returns_dataframe(self):
        """query_historical returns a pd.DataFrame."""
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        orch.register_default_features()
        now = datetime.now(timezone.utc)
        result = orch.query_historical(
            ["rsi"], ["BTCUSDT"],
            now - timedelta(hours=1),
            now + timedelta(hours=1),
        )
        assert isinstance(result, pd.DataFrame)

    def test_query_realtime_returns_dataframe(self):
        """query_realtime returns a pd.DataFrame."""
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        orch.register_default_features()
        result = orch.query_realtime(["rsi"], ["BTCUSDT"])
        assert isinstance(result, pd.DataFrame)


# ===========================================================================
# FP7D1-3 — FP-7C staleness parameter preserved
# ===========================================================================

class TestFP7CStalenessPreserved:
    """Verify FP-7C max_age_seconds parameter was not affected by alias removal."""

    def test_query_realtime_accepts_max_age_seconds(self):
        """query_realtime must accept the optional max_age_seconds parameter (FP-7C)."""
        import inspect
        sig = inspect.signature(FeaturePlatformOrchestrator.query_realtime)
        assert "max_age_seconds" in sig.parameters, (
            "FP-7D-1 regression: max_age_seconds missing from query_realtime signature"
        )

    def test_query_realtime_max_age_seconds_defaults_to_none(self):
        """max_age_seconds must default to None (FP-7C contract)."""
        import inspect
        sig = inspect.signature(FeaturePlatformOrchestrator.query_realtime)
        param = sig.parameters["max_age_seconds"]
        assert param.default is None, (
            f"FP-7D-1 regression: max_age_seconds default is {param.default!r}, expected None"
        )
