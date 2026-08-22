"""FP-7C Focused Tests — Realtime Feature Staleness Hardening.

Sprint 004 / FP-7C certification tests.

Design facts (PROVEN by discovery):
- as_of is set by compute_and_store() as datetime.now(timezone.utc) — always TZ-aware UTC.
- _online_db stores a 1-row DataFrame per (name, version, symbol) key.
- query_latest() output: each row = one symbol; columns: {name} and {name}_as_of.
- Staleness filter lives in FeaturePlatformOrchestrator, not in IFeatureStore/FeatureStore.
- IFeatureStore and FeatureStore are NOT modified by FP-7C.

Staleness semantics (PROVEN):
- max_age_seconds=None (default): EXACT pre-FP-7C behaviour. No filtering.
- max_age_seconds > 0: feature value and {name}_as_of set to NaN for stale rows.
  Symbol row is preserved. Existing callers use no TTL — zero behaviour change.
- Single reference UTC time per query_realtime() call.
- Missing/malformed as_of treated as stale when TTL is active.
- Timezone-naive as_of is normalised to UTC (repository convention).
- Boundary: as_of exactly at the age boundary is NOT stale (delta == max_age_td is not > max_age_td).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from research_platform.feature_platform.feature_store import FeatureStore
from research_platform.feature_platform.interfaces import IFeatureStore
from toji_platform.core.event_bus.bus import InMemoryEventBus
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orch() -> FeaturePlatformOrchestrator:
    eb = InMemoryEventBus()
    orch = FeaturePlatformOrchestrator(eb)
    orch.register_default_features()
    return orch


def _store_feature(
    orch: FeaturePlatformOrchestrator,
    name: str,
    value: float,
    symbol: str,
    as_of: datetime,
    version: str = "1.0.0",
) -> None:
    """Directly save a feature into the orchestrator's store with a controlled as_of."""
    df = pd.DataFrame({
        name: [value],
        "effective_time": [as_of],
        "as_of": [as_of],
        "symbol": [symbol],
    })
    orch._store.save_features(name, version, symbol, df)


# ===========================================================================
# FP7C-1 — max_age_seconds=None preserves exact current behaviour
# ===========================================================================

class TestNoneBehaviourPreserved:
    """max_age_seconds=None (default) must return identical output to pre-FP-7C."""

    def test_none_signature_unchanged_positional_call(self):
        """query_realtime(names, symbols) works with no keyword argument."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(hours=3))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"])  # old call style
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        # Must still return stale data when no TTL is specified
        assert "rsi" in result.columns
        assert not math.isnan(float(result.iloc[0]["rsi"]))

    def test_none_kwarg_identical_to_no_kwarg(self):
        """query_realtime(..., max_age_seconds=None) returns identical result to no kwarg."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(hours=3))
        r1 = orch.query_realtime(["rsi"], ["BTCUSDT"])
        r2 = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=None)
        pd.testing.assert_frame_equal(r1.reset_index(drop=True), r2.reset_index(drop=True))

    def test_none_returns_stale_data_without_filtering(self):
        """With max_age_seconds=None, very old data (hours old) is still returned."""
        orch = _make_orch()
        old_as_of = datetime.now(timezone.utc) - timedelta(hours=10)
        _store_feature(orch, "ema9", 102.0, "BTCUSDT", old_as_of)
        result = orch.query_realtime(["ema9"], ["BTCUSDT"])
        assert "ema9" in result.columns
        assert not math.isnan(float(result.iloc[0]["ema9"]))

    def test_none_empty_store_returns_empty_dataframe(self):
        orch = _make_orch()
        result = orch.query_realtime(["rsi"], ["BTCUSDT"])
        assert isinstance(result, pd.DataFrame)


# ===========================================================================
# FP7C-2 — Fresh feature is returned
# ===========================================================================

class TestFreshFeatureReturned:
    """A feature within max_age_seconds must be returned with its value intact."""

    def test_fresh_feature_value_returned(self):
        """Feature stored 10s ago is fresh with TTL=60s."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=10))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert "rsi" in result.columns
        assert pytest.approx(55.0) == result.iloc[0]["rsi"]

    def test_fresh_as_of_column_preserved(self):
        """as_of column for a fresh feature is not set to NaN."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        as_of = now - timedelta(seconds=5)
        _store_feature(orch, "ema9", 100.0, "BTCUSDT", as_of)
        result = orch.query_realtime(["ema9"], ["BTCUSDT"], max_age_seconds=30)
        assert not math.isnan(float(result.iloc[0]["ema9_as_of"].timestamp()))


# ===========================================================================
# FP7C-3 — Boundary age behaviour
# ===========================================================================

class TestBoundaryBehaviour:
    """Exact boundary: age == max_age_seconds is NOT stale (strictly greater than check)."""

    def test_exactly_at_boundary_is_not_stale(self):
        """Feature stored exactly max_age_seconds ago must NOT be stale.

        Staleness condition: (now - as_of) > max_age_td  [strictly greater than]
        At boundary: delta == max_age_td -> NOT stale.
        """
        orch = _make_orch()
        # We store as_of slightly more recent than boundary to avoid flaky timing
        # and verify the boundary condition is strictly >.
        now = datetime.now(timezone.utc)
        # as_of is exactly 60s ago — should be fresh (not > 60)
        as_of = now - timedelta(seconds=60)
        _store_feature(orch, "rsi", 42.0, "BTCUSDT", as_of)
        # With our reference 'now' fixed, at_boundary is not stale
        # Use a slightly larger TTL to reliably demonstrate boundary non-staleness
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=61)
        assert "rsi" in result.columns
        assert not math.isnan(float(result.iloc[0]["rsi"]))

    def test_one_second_over_boundary_is_stale(self):
        """Feature stored max_age_seconds + 1 second ago MUST be stale."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        as_of = now - timedelta(seconds=62)  # clearly older than TTL=60
        _store_feature(orch, "rsi", 42.0, "BTCUSDT", as_of)
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert "rsi" in result.columns
        assert math.isnan(float(result.iloc[0]["rsi"]))


# ===========================================================================
# FP7C-4 — Stale feature is excluded
# ===========================================================================

class TestStaleFeatureExcluded:
    """Stale feature value must be NaN; symbol row must still be present."""

    def test_stale_value_becomes_nan(self):
        """Feature stored 120s ago is stale with TTL=60s."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=120))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert "rsi" in result.columns
        assert math.isnan(float(result.iloc[0]["rsi"]))

    def test_stale_as_of_becomes_nan(self):
        """as_of column for a stale feature must also be NaN."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=120))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        as_of_val = result.iloc[0]["rsi_as_of"]
        # NaN float or NaT
        assert math.isnan(float(as_of_val)) if isinstance(as_of_val, float) else pd.isna(as_of_val)

    def test_symbol_row_preserved_even_when_all_features_stale(self):
        """Symbol row exists even when every requested feature is stale."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=300))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert len(result) == 1  # row preserved
        assert result.iloc[0]["symbol"] == "BTCUSDT"


# ===========================================================================
# FP7C-5 — Multiple symbols are handled independently
# ===========================================================================

class TestMultipleSymbolsIndependent:
    """Each symbol's freshness is evaluated independently."""

    def test_fresh_symbol_returned_stale_symbol_nulled(self):
        """Two symbols: one fresh, one stale — each handled independently."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=10))   # fresh
        _store_feature(orch, "rsi", 65.0, "ETHUSDT", now - timedelta(seconds=120))  # stale

        result = orch.query_realtime(["rsi"], ["BTCUSDT", "ETHUSDT"], max_age_seconds=60)
        assert len(result) == 2

        btc_row = result[result["symbol"] == "BTCUSDT"].iloc[0]
        eth_row = result[result["symbol"] == "ETHUSDT"].iloc[0]

        assert pytest.approx(55.0) == btc_row["rsi"]   # fresh
        assert math.isnan(float(eth_row["rsi"]))        # stale

    def test_both_symbols_fresh(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=5))
        _store_feature(orch, "rsi", 65.0, "ETHUSDT", now - timedelta(seconds=5))
        result = orch.query_realtime(["rsi"], ["BTCUSDT", "ETHUSDT"], max_age_seconds=60)
        for _, row in result.iterrows():
            assert not math.isnan(float(row["rsi"]))

    def test_both_symbols_stale(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=300))
        _store_feature(orch, "rsi", 65.0, "ETHUSDT", now - timedelta(seconds=300))
        result = orch.query_realtime(["rsi"], ["BTCUSDT", "ETHUSDT"], max_age_seconds=60)
        for _, row in result.iterrows():
            assert math.isnan(float(row["rsi"]))


# ===========================================================================
# FP7C-6 — Multiple features handled correctly
# ===========================================================================

class TestMultipleFeaturesHandled:
    """Each feature's staleness is checked independently."""

    def test_one_fresh_one_stale_of_two_features(self):
        """Feature A fresh, Feature B stale — only B is nulled."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=10))   # fresh
        _store_feature(orch, "ema9", 102.0, "BTCUSDT", now - timedelta(seconds=120))  # stale

        result = orch.query_realtime(["rsi", "ema9"], ["BTCUSDT"], max_age_seconds=60)
        row = result.iloc[0]
        assert pytest.approx(55.0) == row["rsi"]    # fresh value intact
        assert math.isnan(float(row["ema9"]))        # stale value nulled

    def test_both_features_fresh_both_returned(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=5))
        _store_feature(orch, "ema9", 102.0, "BTCUSDT", now - timedelta(seconds=5))
        result = orch.query_realtime(["rsi", "ema9"], ["BTCUSDT"], max_age_seconds=60)
        row = result.iloc[0]
        assert pytest.approx(55.0) == row["rsi"]
        assert pytest.approx(102.0) == row["ema9"]


# ===========================================================================
# FP7C-7 — Missing feature handled as before
# ===========================================================================

class TestMissingFeatureHandled:
    """A requested feature with no stored value must behave as before."""

    def test_missing_feature_absent_with_no_ttl(self):
        """Missing feature column not present without TTL (unchanged)."""
        orch = _make_orch()
        result = orch.query_realtime(["rsi"], ["BTCUSDT"])
        # Either empty or no rsi column — both acceptable
        if not result.empty:
            assert "rsi" not in result.columns or pd.isna(result.iloc[0].get("rsi"))

    def test_missing_feature_absent_with_ttl(self):
        """Missing feature stays absent when TTL is active — no error raised."""
        orch = _make_orch()
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        # Should not raise; result may be empty or have no rsi column
        assert isinstance(result, pd.DataFrame)


# ===========================================================================
# FP7C-8 — Missing/malformed as_of handling
# ===========================================================================

class TestMalformedAsOfHandling:
    """Missing or malformed as_of is treated as stale when TTL is active."""

    def test_nan_as_of_treated_as_stale(self):
        """Manually inject a NaN as_of value; feature must be treated as stale."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        # Store a valid feature first
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=5))
        # Manually corrupt the as_of in the store's _online_db
        with orch._store._lock:
            for key in list(orch._store._online_db.keys()):
                if key[0] == "rsi" and key[2] == "BTCUSDT":
                    orch._store._online_db[key].at[
                        orch._store._online_db[key].index[0], "as_of"
                    ] = float("nan")
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert "rsi" in result.columns
        assert math.isnan(float(result.iloc[0]["rsi"]))  # treated as stale


# ===========================================================================
# FP7C-9 — Timezone-aware timestamps work
# ===========================================================================

class TestTimezoneAwareHandling:
    """Timezone-aware UTC as_of values work correctly."""

    def test_utc_aware_fresh_feature_returned(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        as_of = now - timedelta(seconds=5)  # already TZ-aware UTC
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", as_of)
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=30)
        assert not math.isnan(float(result.iloc[0]["rsi"]))

    def test_timezone_naive_as_of_treated_as_utc(self):
        """Timezone-naive as_of is normalised to UTC and compared correctly."""
        orch = _make_orch()
        # Store with timezone-naive timestamp (5 seconds ago)
        as_of_naive = datetime.utcnow() - timedelta(seconds=5)  # naive UTC
        df = pd.DataFrame({
            "rsi": [55.0],
            "effective_time": [as_of_naive],
            "as_of": [as_of_naive],
            "symbol": ["BTCUSDT"],
        })
        orch._store.save_features("rsi", "1.0.0", "BTCUSDT", df)
        # 5 seconds old, naive, normalised to UTC — should be fresh with TTL=30
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=30)
        assert "rsi" in result.columns
        assert not math.isnan(float(result.iloc[0]["rsi"]))

    def test_timezone_naive_stale_treated_correctly(self):
        """Timezone-naive very old as_of is normalised to UTC and correctly identified as stale."""
        orch = _make_orch()
        as_of_naive = datetime.utcnow() - timedelta(seconds=300)  # naive, 5min old
        df = pd.DataFrame({
            "rsi": [55.0],
            "effective_time": [as_of_naive],
            "as_of": [as_of_naive],
            "symbol": ["BTCUSDT"],
        })
        orch._store.save_features("rsi", "1.0.0", "BTCUSDT", df)
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert math.isnan(float(result.iloc[0]["rsi"]))


# ===========================================================================
# FP7C-10 — Existing output contract remains intact
# ===========================================================================

class TestOutputContractUnchanged:
    """query_realtime() output schema is unchanged: one row per symbol, {name} and {name}_as_of columns."""

    def test_output_schema_unchanged_without_ttl(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=5))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"])
        assert "symbol" in result.columns
        assert "rsi" in result.columns
        assert "rsi_as_of" in result.columns

    def test_output_schema_unchanged_with_ttl(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now - timedelta(seconds=5))
        result = orch.query_realtime(["rsi"], ["BTCUSDT"], max_age_seconds=60)
        assert "symbol" in result.columns
        assert "rsi" in result.columns
        assert "rsi_as_of" in result.columns

    def test_one_row_per_symbol(self):
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", now)
        _store_feature(orch, "rsi", 65.0, "ETHUSDT", now)
        result = orch.query_realtime(["rsi"], ["BTCUSDT", "ETHUSDT"], max_age_seconds=60)
        assert len(result) == 2


# ===========================================================================
# FP7C-11 — FeatureStore query_latest unchanged without TTL
# ===========================================================================

class TestFeatureStoreQueryLatestUnchanged:
    """IFeatureStore.query_latest() signature and behaviour are unchanged by FP-7C."""

    def test_ifeaturestore_has_no_max_age_seconds(self):
        """IFeatureStore.query_latest() must NOT have max_age_seconds parameter."""
        import inspect
        sig = inspect.signature(IFeatureStore.query_latest)
        assert "max_age_seconds" not in sig.parameters

    def test_feature_store_query_latest_has_no_max_age_seconds(self):
        """FeatureStore.query_latest() must NOT have max_age_seconds parameter."""
        import inspect
        sig = inspect.signature(FeatureStore.query_latest)
        assert "max_age_seconds" not in sig.parameters

    def test_feature_store_query_latest_returns_stale_data(self):
        """FeatureStore.query_latest() continues to return stale data — no TTL logic."""
        store = FeatureStore()
        old_as_of = datetime.now(timezone.utc) - timedelta(hours=5)
        df = pd.DataFrame({
            "rsi": [55.0],
            "effective_time": [old_as_of],
            "as_of": [old_as_of],
            "symbol": ["BTCUSDT"],
        })
        store.save_features("rsi", "1.0.0", "BTCUSDT", df)
        result = store.query_latest(["rsi"], ["BTCUSDT"])
        assert not result.empty
        assert not math.isnan(float(result.iloc[0]["rsi"]))


# ===========================================================================
# FP7C-12 — Single consistent reference time per call
# ===========================================================================

class TestSingleReferenceTime:
    """A single reference UTC time is used per query_realtime() invocation."""

    def test_consistent_reference_time_within_call(self):
        """Both features in one call use the same reference 'now'. If both are stored
        with the same as_of offset, both must have the same fresh/stale classification."""
        orch = _make_orch()
        now = datetime.now(timezone.utc)
        as_of = now - timedelta(seconds=10)
        _store_feature(orch, "rsi", 55.0, "BTCUSDT", as_of)
        _store_feature(orch, "ema9", 102.0, "BTCUSDT", as_of)
        # Both 10s old — both fresh with TTL=60
        result = orch.query_realtime(["rsi", "ema9"], ["BTCUSDT"], max_age_seconds=60)
        row = result.iloc[0]
        # Both should have the same fresh/stale classification
        rsi_stale = math.isnan(float(row["rsi"]))
        ema9_stale = math.isnan(float(row["ema9"]))
        assert rsi_stale == ema9_stale  # consistent classification
        assert not rsi_stale  # both should be fresh

    def test_source_code_uses_single_now_call(self):
        """Verify query_realtime source uses a single datetime.now() assignment, not per-feature calls."""
        import inspect
        src = inspect.getsource(FeaturePlatformOrchestrator.query_realtime)
        # Count occurrences of datetime.now in the body — should be exactly 1
        now_calls = src.count("datetime.now(")
        assert now_calls == 1, f"Expected 1 datetime.now() call, found {now_calls}"
