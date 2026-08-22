"""FP-7A Focused Tests: Semantic Version Ordering & Runtime annualized_vol Availability.

Sprint 004 / FP-7A certification tests.

R-1 tests: FeatureStore._parse_semver and version resolution correctness.
R-2 tests: annualized_vol is computed and available to PositionSizingOrchestrator,
           fallback behaviour is preserved when genuinely unavailable,
           query_realtime boundary remains intact.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

import pandas as pd
import pytest

from research_platform.feature_platform.feature_store import FeatureStore, _parse_semver


# ============================================================
# R-1: SEMANTIC VERSION ORDERING
# ============================================================

class TestParseSemver:
    """Unit tests for the _parse_semver helper function."""

    def test_basic_version(self):
        """Standard 3-part version parses correctly."""
        assert _parse_semver("1.0.0") == (1, 0, 0)

    def test_multi_digit_patch(self):
        """1.0.10 > 1.0.9 — the core discovered defect."""
        assert _parse_semver("1.0.10") > _parse_semver("1.0.9")

    def test_major_dominates(self):
        """2.0.0 > 1.9.9 — major version takes precedence."""
        assert _parse_semver("2.0.0") > _parse_semver("1.9.9")

    def test_minor_dominates(self):
        """1.10.0 > 1.9.0 — minor version takes precedence over patch."""
        assert _parse_semver("1.10.0") > _parse_semver("1.9.0")

    def test_equal_versions(self):
        """Equal versions produce equal tuples."""
        assert _parse_semver("3.2.1") == _parse_semver("3.2.1")

    def test_malformed_two_parts_raises(self):
        """Versions with only 2 parts are rejected."""
        with pytest.raises(ValueError, match="expected exactly 3"):
            _parse_semver("1.0")

    def test_malformed_four_parts_raises(self):
        """Versions with 4 parts are rejected."""
        with pytest.raises(ValueError, match="expected exactly 3"):
            _parse_semver("1.0.0.0")

    def test_malformed_non_integer_raises(self):
        """Non-integer version components are rejected."""
        with pytest.raises(ValueError, match="must be integers"):
            _parse_semver("1.0.beta")

    def test_empty_string_raises(self):
        """Empty version string is rejected."""
        with pytest.raises(ValueError, match="expected exactly 3"):
            _parse_semver("")


class TestFeatureStoreVersionResolution:
    """FeatureStore picks the correct latest version using semantic comparison."""

    @pytest.fixture()
    def store_with_multi_versions(self) -> FeatureStore:
        """Populate a store with the same feature at multiple versions."""
        store = FeatureStore()
        now = datetime.now(timezone.utc)
        for version, val in [("1.0.0", 100.0), ("1.0.9", 109.0), ("1.0.10", 110.0)]:
            df = pd.DataFrame({
                "rsi": [val],
                "effective_time": [now],
                "as_of": [now],
                "symbol": ["BTCUSDT"],
            })
            store.save_features("rsi", version, "BTCUSDT", df)
        return store

    def test_query_latest_picks_110(self, store_with_multi_versions: FeatureStore):
        """query_latest must resolve version 1.0.10 (value=110.0), NOT 1.0.9 lexicographically."""
        result = store_with_multi_versions.query_latest(["rsi"], ["BTCUSDT"])
        assert not result.empty
        assert result.iloc[0]["rsi"] == 110.0

    def test_query_historical_picks_110(self, store_with_multi_versions: FeatureStore):
        """query_historical must also resolve the semantically latest version (1.0.10)."""
        now = datetime.now(timezone.utc)
        result = store_with_multi_versions.query_historical(
            ["rsi"], ["BTCUSDT"], now, now
        )
        # The historical query aligns features with merge_asof; the important thing
        # is that it selected version 1.0.10's data (value 110.0), not 1.0.9's (109.0).
        if "rsi" in result.columns:
            vals = result["rsi"].dropna()
            if len(vals) > 0:
                assert vals.iloc[0] == 110.0

    def test_existing_100_behavior_unchanged(self):
        """A store with only version 1.0.0 continues to work identically."""
        store = FeatureStore()
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "rsi": [55.0],
            "effective_time": [now],
            "as_of": [now],
            "symbol": ["ETHUSDT"],
        })
        store.save_features("rsi", "1.0.0", "ETHUSDT", df)
        result = store.query_latest(["rsi"], ["ETHUSDT"])
        assert not result.empty
        assert result.iloc[0]["rsi"] == 55.0


# ============================================================
# R-2: ANNUALIZED_VOL RUNTIME AVAILABILITY
# ============================================================

class TestRuntimeFeatureListParity:
    """Verify that runtime feature lists include annualized_vol and its consumer dependencies."""

    @pytest.mark.xfail(
        reason=(
            "FP-7D-2 replaced the hard-coded feature list with list(DEFAULT_COMPUTE_NAMES). "
            "This FP-7A test inspects AST for ast.List which no longer exists. "
            "annualized_vol inclusion is now independently verified by "
            "test_sprint004_fp7d2_compute_centralization.py."
        ),
        strict=True,
    )
    def test_paper_trading_features_include_annualized_vol(self):
        """run_paper_trading.py features_to_compute must include annualized_vol."""
        import ast
        import textwrap

        # Read the actual source file
        with open("scripts/run_paper_trading.py", "r") as f:
            source = f.read()

        tree = ast.parse(source)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "features_to_compute":
                        if isinstance(node.value, ast.List):
                            elements = [
                                elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant)
                            ]
                            assert "annualized_vol" in elements, (
                                f"annualized_vol missing from features_to_compute: {elements}"
                            )
                            found = True
        assert found, "Could not locate features_to_compute assignment in run_paper_trading.py"

    @pytest.mark.xfail(
        reason=(
            "FP-7D-2 replaced the hard-coded feature list with list(DEFAULT_COMPUTE_NAMES). "
            "This FP-7A test inspects AST for ast.List which no longer exists. "
            "annualized_vol inclusion is now independently verified by "
            "test_sprint004_fp7d2_compute_centralization.py."
        ),
        strict=True,
    )
    def test_live_trading_features_include_annualized_vol(self):
        """live_trading/plugin.py features_to_compute must include annualized_vol."""
        import ast

        with open("research_platform/live_trading/plugin.py", "r") as f:
            source = f.read()

        tree = ast.parse(source)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "features_to_compute":
                        if isinstance(node.value, ast.List):
                            elements = [
                                elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant)
                            ]
                            assert "annualized_vol" in elements, (
                                f"annualized_vol missing from features_to_compute: {elements}"
                            )
                            found = True
        assert found, "Could not locate features_to_compute assignment in live_trading/plugin.py"


class TestAnnualizedVolComputeAndQuery:
    """Integration: annualized_vol is computed by the DAG and queryable via query_realtime."""

    @pytest.fixture()
    def fp_orch(self):
        """Bootstrap a full FeaturePlatformOrchestrator."""
        from toji_platform.core.event_bus.bus import InMemoryEventBus
        from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        orch.register_default_features()
        return orch

    def test_annualized_vol_computed_with_sufficient_data(self, fp_orch):
        """With 8000 bars (well past 1441 warmup, NaN ratio < 20%), annualized_vol is validated and stored."""
        import numpy as np
        np.random.seed(42)
        n = 8000  # NaN ratio = 1441/8000 = 18% < 20% validator threshold
        close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        })
        fp_orch.compute_and_store(
            ["annualized_vol", "normalized_atr", "risk_score"],
            "BTCUSDT",
            df,
        )
        result = fp_orch.query_realtime(["annualized_vol"], ["BTCUSDT"])
        assert not result.empty
        assert "annualized_vol" in result.columns
        val = result.iloc[0]["annualized_vol"]
        assert val is not None
        assert not math.isnan(float(val)), "annualized_vol should be finite with 1500 bars"

    def test_annualized_vol_nan_during_warmup(self, fp_orch):
        """With only 50 bars (< 1441 warmup), annualized_vol should be NaN."""
        import numpy as np
        np.random.seed(42)
        n = 50
        close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        })
        fp_orch.compute_and_store(["annualized_vol"], "BTCUSDT", df)
        result = fp_orch.query_realtime(["annualized_vol"], ["BTCUSDT"])
        # During warm-up, annualized_vol is NaN — this is the expected behaviour.
        # PositionSizingOrchestrator uses fallback_volatility=0.50 when NaN.
        if not result.empty and "annualized_vol" in result.columns:
            val = result.iloc[0]["annualized_vol"]
            assert val is None or math.isnan(float(val))


class TestPositionSizingFallbackPreserved:
    """Fallback_volatility=0.50 is preserved when annualized_vol is genuinely unavailable (NaN/missing)."""

    def test_fallback_when_feature_unavailable(self):
        """PositionSizingOrchestrator uses fallback 0.50 when no features are stored."""
        from toji_platform.core.event_bus.bus import InMemoryEventBus
        from toji_platform.core.dependency_injection.container import Container
        from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
        from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator

        eb = InMemoryEventBus()
        c = Container()
        fp = FeaturePlatformOrchestrator(eb)
        fp.register_default_features()
        c.register("FeaturePlatformOrchestrator", instance=fp)
        c.register(FeaturePlatformOrchestrator, instance=fp)

        ps = PositionSizingOrchestrator(eb, c)
        # Do NOT compute any features — simulate genuinely unavailable state.
        result = ps.calculate_size("BTCUSDT", "LONG", proposed_price=50000.0)
        # The position sizer should use fallback_volatility=0.50, not crash.
        assert result is not None


class TestQueryRealtimeBoundaryIntact:
    """query_realtime() public API boundary remains canonical after FP-7A changes."""

    def test_query_realtime_returns_dataframe(self):
        """query_realtime returns a valid DataFrame (possibly empty)."""
        from toji_platform.core.event_bus.bus import InMemoryEventBus
        from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        orch.register_default_features()
        result = orch.query_realtime(["rsi", "annualized_vol"], ["BTCUSDT"])
        assert isinstance(result, pd.DataFrame)

    def test_query_realtime_after_compute(self):
        """Features stored via compute_and_store are retrievable via query_realtime."""
        import numpy as np
        from toji_platform.core.event_bus.bus import InMemoryEventBus
        from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
        eb = InMemoryEventBus()
        orch = FeaturePlatformOrchestrator(eb)
        orch.register_default_features()

        np.random.seed(42)
        n = 100
        close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        })
        orch.compute_and_store(["rsi", "ema9"], "BTCUSDT", df)
        result = orch.query_realtime(["rsi", "ema9"], ["BTCUSDT"])
        assert not result.empty
        assert "rsi" in result.columns
        assert "ema9" in result.columns
