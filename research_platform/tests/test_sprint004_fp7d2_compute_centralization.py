"""FP-7D-2 Focused Tests — Compute Site Centralization.

Sprint 004 / FP-7D-2 certification tests.

FP-7D-2 introduced DEFAULT_COMPUTE_NAMES — an immutable tuple derived from
DEFAULT_FEATURE_DEFINITIONS — and replaced the duplicated hard-coded feature
lists in run_paper_trading.py and live_trading/plugin.py.

Tests verify:
1.  DEFAULT_COMPUTE_NAMES exists.
2.  DEFAULT_COMPUTE_NAMES is an immutable tuple.
3.  DEFAULT_COMPUTE_NAMES exactly equals the names from DEFAULT_FEATURE_DEFINITIONS.
4.  DEFAULT_COMPUTE_NAMES contains exactly the canonical 21 features.
5.  DEFAULT_COMPUTE_NAMES has no duplicates.
6.  DEFAULT_COMPUTE_NAMES matches FeaturePipeline transformer keys.
7.  Paper trading uses DEFAULT_COMPUTE_NAMES (source inspection).
8.  Live trading uses DEFAULT_COMPUTE_NAMES (source inspection).
9.  query_historical() remains intact.
10. query_realtime(max_age_seconds=None) FP-7C contract remains intact.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from research_platform.feature_platform.orchestrator import (
    DEFAULT_COMPUTE_NAMES,
    DEFAULT_FEATURE_DEFINITIONS,
    FeaturePlatformOrchestrator,
)
from research_platform.feature_platform.feature_pipeline import FeaturePipeline
from research_platform.feature_platform.dependency_graph import DependencyGraph
from toji_platform.core.event_bus.bus import InMemoryEventBus

# The canonical 21 feature names (order-independent — verified by set equality).
CANONICAL_21 = {
    "open", "high", "low", "close", "volume",
    "log_return", "atr", "ema9", "ema21", "ema50",
    "rsi", "volume_change", "support", "resistance",
    "rolling_std", "normalized_atr", "annualized_vol",
    "breakout", "trend", "risk_score", "signal",
}


# ===========================================================================
# FP7D2-1 — DEFAULT_COMPUTE_NAMES existence and immutability
# ===========================================================================

class TestDefaultComputeNamesExistenceAndType:
    """DEFAULT_COMPUTE_NAMES must exist and be immutable."""

    def test_default_compute_names_exists(self):
        """DEFAULT_COMPUTE_NAMES is importable from orchestrator module."""
        assert DEFAULT_COMPUTE_NAMES is not None

    def test_default_compute_names_is_tuple(self):
        """DEFAULT_COMPUTE_NAMES must be a tuple (immutable)."""
        assert isinstance(DEFAULT_COMPUTE_NAMES, tuple), (
            f"FP-7D-2 FAIL: DEFAULT_COMPUTE_NAMES is {type(DEFAULT_COMPUTE_NAMES).__name__}, "
            f"expected tuple"
        )

    def test_default_compute_names_is_not_list(self):
        """DEFAULT_COMPUTE_NAMES must NOT be a mutable list."""
        assert not isinstance(DEFAULT_COMPUTE_NAMES, list)


# ===========================================================================
# FP7D2-2 — Derivation from DEFAULT_FEATURE_DEFINITIONS
# ===========================================================================

class TestDerivationFromDefinitions:
    """DEFAULT_COMPUTE_NAMES must be derived from DEFAULT_FEATURE_DEFINITIONS."""

    def test_exactly_equals_definition_names(self):
        """DEFAULT_COMPUTE_NAMES must equal tuple(r.name for r in DEFAULT_FEATURE_DEFINITIONS)."""
        expected = tuple(record.name for record in DEFAULT_FEATURE_DEFINITIONS)
        assert DEFAULT_COMPUTE_NAMES == expected, (
            f"FP-7D-2 FAIL: DEFAULT_COMPUTE_NAMES drifted from DEFAULT_FEATURE_DEFINITIONS.\n"
            f"Expected: {expected}\n"
            f"Got:      {DEFAULT_COMPUTE_NAMES}"
        )

    def test_contains_exactly_21_features(self):
        """DEFAULT_COMPUTE_NAMES must contain exactly 21 canonical features."""
        assert len(DEFAULT_COMPUTE_NAMES) == 21, (
            f"FP-7D-2 FAIL: expected 21 features, got {len(DEFAULT_COMPUTE_NAMES)}"
        )

    def test_no_duplicate_names(self):
        """DEFAULT_COMPUTE_NAMES must have no duplicate feature names."""
        assert len(DEFAULT_COMPUTE_NAMES) == len(set(DEFAULT_COMPUTE_NAMES)), (
            f"FP-7D-2 FAIL: duplicates found in DEFAULT_COMPUTE_NAMES"
        )

    def test_canonical_21_set_match(self):
        """DEFAULT_COMPUTE_NAMES as a set must equal the canonical 21-feature set."""
        assert set(DEFAULT_COMPUTE_NAMES) == CANONICAL_21, (
            f"FP-7D-2 FAIL: set mismatch.\n"
            f"Missing: {CANONICAL_21 - set(DEFAULT_COMPUTE_NAMES)}\n"
            f"Extra:   {set(DEFAULT_COMPUTE_NAMES) - CANONICAL_21}"
        )


# ===========================================================================
# FP7D2-3 — Transformer parity guard
# ===========================================================================

class TestTransformerParityGuard:
    """DEFAULT_COMPUTE_NAMES must match FeaturePipeline._transformers keys."""

    def test_transformer_keys_match_compute_names(self):
        """FeaturePipeline transformer registry must have exactly the same feature names."""
        dep_graph = DependencyGraph()
        pipeline = FeaturePipeline(dep_graph)
        transformer_keys = set(pipeline._transformers.keys())
        compute_names_set = set(DEFAULT_COMPUTE_NAMES)

        assert transformer_keys == compute_names_set, (
            f"FP-7D-2 PARITY GUARD FAIL: transformer-definition drift.\n"
            f"In definitions but not in transformers: {compute_names_set - transformer_keys}\n"
            f"In transformers but not in definitions: {transformer_keys - compute_names_set}"
        )


# ===========================================================================
# FP7D2-4 — Paper trading uses DEFAULT_COMPUTE_NAMES (source inspection)
# ===========================================================================

class TestPaperTradingCentralized:
    """Paper trading must use DEFAULT_COMPUTE_NAMES, not a hard-coded list."""

    def test_paper_trading_imports_default_compute_names(self):
        """run_paper_trading.py must import DEFAULT_COMPUTE_NAMES."""
        paper_path = Path(__file__).resolve().parents[2] / "scripts" / "run_paper_trading.py"
        source = paper_path.read_text()
        assert "DEFAULT_COMPUTE_NAMES" in source, (
            "FP-7D-2 FAIL: run_paper_trading.py does not reference DEFAULT_COMPUTE_NAMES"
        )

    def test_paper_trading_no_hardcoded_21_feature_list(self):
        """run_paper_trading.py must NOT contain the old hard-coded 21-feature list."""
        paper_path = Path(__file__).resolve().parents[2] / "scripts" / "run_paper_trading.py"
        source = paper_path.read_text()
        # The old list contained this exact FP-7A comment block.
        # Its absence proves the hard-coded list was removed.
        assert "FP-7A: Features required by downstream consumers but previously omitted." not in source, (
            "FP-7D-2 FAIL: run_paper_trading.py still contains the old hard-coded feature list"
        )


# ===========================================================================
# FP7D2-5 — Live trading uses DEFAULT_COMPUTE_NAMES (source inspection)
# ===========================================================================

class TestLiveTradingCentralized:
    """Live trading must use DEFAULT_COMPUTE_NAMES with lazy import."""

    def test_live_trading_references_default_compute_names(self):
        """live_trading/plugin.py must reference DEFAULT_COMPUTE_NAMES."""
        live_path = (
            Path(__file__).resolve().parents[1] / "live_trading" / "plugin.py"
        )
        source = live_path.read_text()
        assert "DEFAULT_COMPUTE_NAMES" in source, (
            "FP-7D-2 FAIL: live_trading/plugin.py does not reference DEFAULT_COMPUTE_NAMES"
        )

    def test_live_trading_no_hardcoded_21_feature_list(self):
        """live_trading/plugin.py must NOT contain the old hard-coded 21-feature list."""
        live_path = (
            Path(__file__).resolve().parents[1] / "live_trading" / "plugin.py"
        )
        source = live_path.read_text()
        assert "FP-7A: Features required by downstream consumers but previously omitted." not in source, (
            "FP-7D-2 FAIL: live_trading/plugin.py still contains the old hard-coded feature list"
        )

    def test_live_trading_import_is_lazy_not_top_level(self):
        """live_trading/plugin.py must NOT import DEFAULT_COMPUTE_NAMES at top level."""
        live_path = (
            Path(__file__).resolve().parents[1] / "live_trading" / "plugin.py"
        )
        source = live_path.read_text()
        tree = ast.parse(source)

        # Check top-level import statements only (not nested in classes/functions)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "orchestrator" in node.module:
                    imported_names = [alias.name for alias in node.names]
                    assert "DEFAULT_COMPUTE_NAMES" not in imported_names, (
                        "FP-7D-2 FAIL: DEFAULT_COMPUTE_NAMES is imported at top level "
                        "in live_trading/plugin.py — must be lazy"
                    )


# ===========================================================================
# FP7D2-6 — Canonical APIs remain intact
# ===========================================================================

class TestCanonicalAPIsIntact:
    """query_historical() and query_realtime() must remain unchanged."""

    def test_query_historical_exists(self):
        """query_historical must remain on FeaturePlatformOrchestrator."""
        assert hasattr(FeaturePlatformOrchestrator, "query_historical")
        assert callable(FeaturePlatformOrchestrator.query_historical)

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

    def test_query_realtime_max_age_seconds_intact(self):
        """query_realtime must accept max_age_seconds=None (FP-7C contract)."""
        sig = inspect.signature(FeaturePlatformOrchestrator.query_realtime)
        assert "max_age_seconds" in sig.parameters
        assert sig.parameters["max_age_seconds"].default is None

    def test_query_history_remains_absent(self):
        """query_history must NOT exist (FP-7D-1 removal)."""
        assert not hasattr(FeaturePlatformOrchestrator, "query_history"), (
            "FP-7D-2 regression: query_history was reintroduced"
        )
