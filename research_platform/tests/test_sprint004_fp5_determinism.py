"""SPRINT-004 FP-5 — Feature Pipeline Determinism Validation
=============================================================

Certification requirements (from SPRINT-004-FP5-DISCOVERY-GATE.md):

    A == B numeric feature values
    A == B column order
    A == B row order
    A == B NaN/null positions
    A == B index semantics
    SHA256(A) == SHA256(B)

Timestamp contract:
    as_of_time = fixed deterministic value
    effective_time = as_of  (ND-1b fix in orchestrator.py, FP-5 Phase 1)

ND-2 through ND-8 (model metadata timestamps / validation UUIDs) are deferred
advisories — not tested here per OQ-FP5-3 CTO decision.

Predecessor certification: FP-1, FP-2, FP-3D, FP-4 — CERTIFIED PASS (frozen).
ADR-001: PriceActionOrchestrator.get_atr() is canonical ATR. FP-ATR is internal DAG only.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from research_platform.feature_platform.dependency_graph import DependencyGraph
from research_platform.feature_platform.feature_pipeline import FeaturePipeline
from research_platform.feature_platform.models import FeatureRecord
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator

# ============================================================
# SYNTHETIC DATA CONTRACT
# ============================================================
# - 500 1-minute OHLCV bars
# - UTC timestamps, monotonically increasing
# - Deterministic: no wall-clock, no unseeded random
# - OHLCV invariants:
#     open > 0
#     high >= max(open, close)
#     low  <= min(open, close)
#     volume >= 0

_NUM_BARS: int = 500
_CANONICAL_SYMBOL: str = "BTCUSDT"
_FIXED_EPOCH: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # deterministic reference time


def _generate_synthetic_bars(num_bars: int = _NUM_BARS) -> pd.DataFrame:
    """Generate a fully deterministic 500-bar 1-minute OHLCV DataFrame.

    Uses a fixed seed and simple arithmetic price walk — no wall-clock,
    no unseeded randomness, no datetime.now().  The same call always returns
    the same DataFrame.
    """
    rng = np.random.default_rng(seed=42)  # fixed seed — deterministic

    # Build a simple geometric random walk for close prices
    base_price: float = 50_000.0
    log_returns = rng.normal(loc=0.0, scale=0.0005, size=num_bars)
    close_prices = base_price * np.exp(np.cumsum(log_returns))

    # Derive OHLC that satisfy the canonical OHLCV invariants
    noise_pct = 0.002
    noise = rng.uniform(low=0.0, high=noise_pct, size=num_bars)

    open_prices = close_prices * (1.0 + rng.uniform(-noise_pct, noise_pct, size=num_bars))
    high_prices = np.maximum(open_prices, close_prices) * (1.0 + noise)
    low_prices  = np.minimum(open_prices, close_prices) * (1.0 - noise)
    volume      = rng.uniform(low=1.0, high=100.0, size=num_bars)

    # Monotonically increasing UTC timestamps from _FIXED_EPOCH
    timestamps = [_FIXED_EPOCH + timedelta(minutes=i) for i in range(num_bars)]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open":  open_prices,
        "high":  high_prices,
        "low":   low_prices,
        "close": close_prices,
        "volume": volume,
    })


# ============================================================
# FEATURE SET FOR FP-5 TESTS
# ============================================================
# Subset covering all transformer families, including warm-up-sensitive ones.
# (annualized_vol requires 1440-bar warm-up — deliberately excluded so tests
#  can verify meaningful non-NaN values without a 1440-bar sequence.)
_FP5_FEATURE_NAMES: List[str] = [
    "close", "open", "high", "low", "volume",
    "log_return", "rolling_std",
    "atr", "normalized_atr", "risk_score", "signal",
    "ema9", "ema21", "ema50",
    "rsi", "volume_change",
    "support", "resistance", "breakout", "trend",
]

# FeatureRecord stubs — uuid is deterministic (fixed strings) to avoid ND-2 impact
_FP5_FEATURE_RECORDS: List[FeatureRecord] = [
    FeatureRecord(uuid="fp5-close-v1",        name="close",         display_name="CLOSE",         description="", formula="", category="Price",     subcategory="Raw",       owner="quants", author="CTO", version="1.0.0", dependencies=[],                        update_frequency="1m", warmup_length=0,  lookback_window=0,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-open-v1",         name="open",          display_name="OPEN",          description="", formula="", category="Price",     subcategory="Raw",       owner="quants", author="CTO", version="1.0.0", dependencies=[],                        update_frequency="1m", warmup_length=0,  lookback_window=0,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-high-v1",         name="high",          display_name="HIGH",          description="", formula="", category="Price",     subcategory="Raw",       owner="quants", author="CTO", version="1.0.0", dependencies=[],                        update_frequency="1m", warmup_length=0,  lookback_window=0,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-low-v1",          name="low",           display_name="LOW",           description="", formula="", category="Price",     subcategory="Raw",       owner="quants", author="CTO", version="1.0.0", dependencies=[],                        update_frequency="1m", warmup_length=0,  lookback_window=0,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-volume-v1",       name="volume",        display_name="VOLUME",        description="", formula="", category="Volume",    subcategory="Raw",       owner="quants", author="CTO", version="1.0.0", dependencies=[],                        update_frequency="1m", warmup_length=0,  lookback_window=0,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-logret-v1",       name="log_return",    display_name="LOG_RETURN",    description="", formula="", category="Indicator", subcategory="Derived",   owner="quants", author="CTO", version="1.0.0", dependencies=["close"],                 update_frequency="1m", warmup_length=1,  lookback_window=1,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-rstd-v1",         name="rolling_std",   display_name="ROLLING_STD",   description="", formula="", category="Indicator", subcategory="Derived",   owner="quants", author="CTO", version="1.0.0", dependencies=["log_return"],            update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"),
    FeatureRecord(uuid="fp5-atr-v1",          name="atr",           display_name="ATR",           description="", formula="", category="Indicator", subcategory="Vol",       owner="quants", author="CTO", version="1.0.0", dependencies=["high", "low", "close"],  update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"),
    FeatureRecord(uuid="fp5-natr-v1",         name="normalized_atr",display_name="NORMALIZED_ATR",description="", formula="", category="Indicator", subcategory="Vol",       owner="quants", author="CTO", version="1.0.0", dependencies=["atr", "close"],          update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"),
    FeatureRecord(uuid="fp5-rscore-v1",       name="risk_score",    display_name="RISK_SCORE",    description="", formula="", category="Indicator", subcategory="Risk",      owner="quants", author="CTO", version="1.0.0", dependencies=["normalized_atr"],        update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"),
    FeatureRecord(uuid="fp5-signal-v1",       name="signal",        display_name="SIGNAL",        description="", formula="", category="Indicator", subcategory="Signal",    owner="quants", author="CTO", version="1.0.0", dependencies=["risk_score"],            update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"),
    FeatureRecord(uuid="fp5-ema9-v1",         name="ema9",          display_name="EMA9",          description="", formula="", category="Indicator", subcategory="Trend",     owner="quants", author="CTO", version="1.0.0", dependencies=["close"],                 update_frequency="1m", warmup_length=9,  lookback_window=9,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-ema21-v1",        name="ema21",         display_name="EMA21",         description="", formula="", category="Indicator", subcategory="Trend",     owner="quants", author="CTO", version="1.0.0", dependencies=["close"],                 update_frequency="1m", warmup_length=21, lookback_window=21, required_resolution="1m"),
    FeatureRecord(uuid="fp5-ema50-v1",        name="ema50",         display_name="EMA50",         description="", formula="", category="Indicator", subcategory="Trend",     owner="quants", author="CTO", version="1.0.0", dependencies=["close"],                 update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"),
    FeatureRecord(uuid="fp5-rsi-v1",          name="rsi",           display_name="RSI",           description="", formula="", category="Indicator", subcategory="Momentum",  owner="quants", author="CTO", version="1.0.0", dependencies=["close"],                 update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"),
    FeatureRecord(uuid="fp5-volchg-v1",       name="volume_change", display_name="VOLUME_CHANGE", description="", formula="", category="Volume",    subcategory="Derived",   owner="quants", author="CTO", version="1.0.0", dependencies=["volume"],                update_frequency="1m", warmup_length=1,  lookback_window=1,  required_resolution="1m"),
    FeatureRecord(uuid="fp5-support-v1",      name="support",       display_name="SUPPORT",       description="", formula="", category="Level",     subcategory="Support",   owner="quants", author="CTO", version="1.0.0", dependencies=["low"],                   update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"),
    FeatureRecord(uuid="fp5-resist-v1",       name="resistance",    display_name="RESISTANCE",    description="", formula="", category="Level",     subcategory="Resistance",owner="quants", author="CTO", version="1.0.0", dependencies=["high"],                  update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"),
    FeatureRecord(uuid="fp5-breakout-v1",     name="breakout",      display_name="BREAKOUT",      description="", formula="", category="Signal",    subcategory="Breakout",  owner="quants", author="CTO", version="1.0.0", dependencies=["close", "resistance", "support"], update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"),
    FeatureRecord(uuid="fp5-trend-v1",        name="trend",         display_name="TREND",         description="", formula="", category="Signal",    subcategory="Trend",     owner="quants", author="CTO", version="1.0.0", dependencies=["ema9", "ema21"],         update_frequency="1m", warmup_length=21, lookback_window=21, required_resolution="1m"),
]

# Timestamp-carrying columns to exclude from SHA-256 numeric fingerprint
_TIMESTAMP_COLUMNS: frozenset = frozenset({"as_of", "effective_time", "timestamp"})


def _build_orchestrator() -> FeaturePlatformOrchestrator:
    """Build a fresh, fully registered FeaturePlatformOrchestrator with a mock EventBus."""
    orch = FeaturePlatformOrchestrator(event_bus=MagicMock())
    for record in _FP5_FEATURE_RECORDS:
        try:
            orch.register_feature(record)
        except ValueError:
            pass  # idempotent registration
    return orch


def _sha256_numeric_fingerprint(df: pd.DataFrame) -> str:
    """Canonical SHA-256 fingerprint of numeric feature columns only.

    Determinism contract:
    - Timestamp columns (as_of, effective_time, timestamp) are excluded.
    - Columns are sorted alphabetically for stability.
    - NaN values are canonically represented as the string "NaN".
    - +Inf / -Inf are canonically represented as "+Inf" / "-Inf".
    - Row and column order are preserved (columns sorted, rows in DataFrame order).
    """
    numeric_cols = sorted([c for c in df.columns if c not in _TIMESTAMP_COLUMNS])

    rows = []
    for _, row in df[numeric_cols].iterrows():
        serialized_row = {}
        for col in numeric_cols:
            val = row[col]
            if isinstance(val, float):
                if math.isnan(val):
                    serialized_row[col] = "NaN"
                elif math.isinf(val):
                    serialized_row[col] = "+Inf" if val > 0 else "-Inf"
                else:
                    serialized_row[col] = val
            else:
                serialized_row[col] = val
        rows.append(serialized_row)

    canonical_str = json.dumps(rows, sort_keys=False, ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


# ============================================================
# TEST 1 — Synthetic bar replay executes cleanly
# ============================================================

def test_fp5_1_synthetic_bar_replay_executes() -> None:
    """FP-5 Requirement 1: 500-bar deterministic replay processes through
    compute_and_store() without error and yields a non-empty output DataFrame.

    - No wall-clock datetime in synthetic input.
    - No unseeded random.
    - Fixed as_of_time supplied to control ND-1a and ND-1b.
    """
    bars_df = _generate_synthetic_bars(num_bars=_NUM_BARS)
    orch = _build_orchestrator()

    output_df = orch.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=bars_df.copy(),
        as_of_time=_FIXED_EPOCH,
    )

    # Non-empty output
    assert output_df is not None
    assert len(output_df) == _NUM_BARS

    # All requested feature columns are present
    for feature in _FP5_FEATURE_NAMES:
        assert feature in output_df.columns, f"Missing feature column: {feature}"

    # ND-1b fix: effective_time must equal as_of — directly assert the approved production contract.
    assert "as_of" in output_df.columns
    assert "effective_time" in output_df.columns

    # Verify as_of is the injected fixed value on every row.
    assert (output_df["as_of"] == _FIXED_EPOCH).all(), (
        "as_of column does not equal the injected as_of_time on every row"
    )

    # Required Fix 2 (CTO): directly assert effective_time == _FIXED_EPOCH.
    # Our synthetic df has a 'timestamp' column, so the orchestrator routes effective_time
    # from output_df["timestamp"] (not from as_of). Timestamps in the synthetic sequence
    # start at _FIXED_EPOCH (bar 0) and increment by 1 minute per bar. The key contract
    # is that effective_time is never assigned via a second independent datetime.now() call.
    # Assert ND-1b elimination: the fallback branch (no timestamp column) would set
    # effective_time = as_of. Prove it holds for a DataFrame without timestamp column.
    import pandas as pd  # pd already imported at module level; re-imported here for local clarity
    bars_no_ts = bars_df.drop(columns=["timestamp"])
    orch_no_ts = _build_orchestrator()
    out_no_ts = orch_no_ts.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=bars_no_ts.copy(),
        as_of_time=_FIXED_EPOCH,
    )
    # When no timestamp column: effective_time must equal as_of (= _FIXED_EPOCH)
    assert (out_no_ts["effective_time"] == _FIXED_EPOCH).all(), (
        "effective_time does not equal as_of (_FIXED_EPOCH) in the no-timestamp branch — "
        "ND-1b fix is not working correctly"
    )
    assert (out_no_ts["effective_time"] == out_no_ts["as_of"]).all(), (
        "effective_time != as_of — ND-1b contract violated"
    )

    print(f"\n[FP5-1] PASS: 500-bar replay → {len(output_df)} rows, "
          f"{len([c for c in output_df.columns if c not in _TIMESTAMP_COLUMNS])} numeric feature columns.")
    print(f"[FP5-1] ND-1b verified: effective_time == as_of == _FIXED_EPOCH in no-timestamp branch.")


# ============================================================
# TEST 2 — Two-pass numeric determinism
# ============================================================

def test_fp5_2_two_pass_numeric_determinism() -> None:
    """FP-5 Requirement 2: Two independent FeaturePlatformOrchestrator instances,
    each fed identical 500-bar DataFrames and the same fixed as_of_time, must
    produce bit-identical numeric feature output columns.

    Assertions:
    - Column names identical (same set and order after sort)
    - Row count identical
    - Numeric values bit-identical (no floating-point drift between runs)
    - NaN positions identical
    - Index semantics identical
    """
    bars_a = _generate_synthetic_bars(num_bars=_NUM_BARS)
    bars_b = _generate_synthetic_bars(num_bars=_NUM_BARS)

    # Verify the two generated DataFrames are identical (synthetic generator contract)
    pd.testing.assert_frame_equal(bars_a, bars_b, check_exact=True)

    # Independent orchestrator instances — Run A
    orch_a = _build_orchestrator()
    out_a = orch_a.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=bars_a.copy(),
        as_of_time=_FIXED_EPOCH,
    )

    # Independent orchestrator instances — Run B
    orch_b = _build_orchestrator()
    out_b = orch_b.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=bars_b.copy(),
        as_of_time=_FIXED_EPOCH,
    )

    numeric_cols_a = sorted([c for c in out_a.columns if c not in _TIMESTAMP_COLUMNS])
    numeric_cols_b = sorted([c for c in out_b.columns if c not in _TIMESTAMP_COLUMNS])

    # Column set identity
    assert numeric_cols_a == numeric_cols_b, (
        f"Column sets differ:\n  A: {numeric_cols_a}\n  B: {numeric_cols_b}"
    )

    # Row count identity
    assert len(out_a) == len(out_b), (
        f"Row counts differ: A={len(out_a)}, B={len(out_b)}"
    )

    # Required Fix 1 (CTO): Assert index semantics BEFORE any reset_index.
    pd.testing.assert_index_equal(
        out_a.index,
        out_b.index,
        exact=True,
    )

    # Numeric value identity — must be bit-for-bit equal
    pd.testing.assert_frame_equal(
        out_a[numeric_cols_a].reset_index(drop=True),
        out_b[numeric_cols_b].reset_index(drop=True),
        check_exact=True,
        check_names=True,
        check_like=False,
    )

    # NaN position identity
    nan_a = out_a[numeric_cols_a].isna()
    nan_b = out_b[numeric_cols_b].isna()
    assert nan_a.equals(nan_b), "NaN positions differ between Run A and Run B"

    print(f"\n[FP5-2] PASS: Index equality confirmed (assert_index_equal exact=True).")
    print(f"[FP5-2] PASS: Two-pass bit-identical numeric determinism confirmed "
          f"across {len(numeric_cols_a)} feature columns × {len(out_a)} rows.")


# ============================================================
# TEST 3 — SHA-256 canonical fingerprint
# ============================================================

def test_fp5_3_sha256_canonical_fingerprint() -> None:
    """FP-5 Requirement 3: Canonical SHA-256 fingerprint of numeric feature output
    columns (timestamp-excluded) is identical between Run A and Run B.

    Canonical serialization:
    - Timestamp columns excluded: as_of, effective_time, timestamp
    - Columns sorted alphabetically
    - NaN -> "NaN" (canonical string, never Python float NaN in JSON)
    - +Inf -> "+Inf", -Inf -> "-Inf"
    - Row order preserved (DataFrame order)
    - No allow_nan=True in json.dumps to prevent silent JSON NaN serialization

    SHA-256 assertion: hash_a == hash_b (full 64-character hex)
    """
    orch_a = _build_orchestrator()
    out_a = orch_a.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=_generate_synthetic_bars().copy(),
        as_of_time=_FIXED_EPOCH,
    )

    orch_b = _build_orchestrator()
    out_b = orch_b.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=_generate_synthetic_bars().copy(),
        as_of_time=_FIXED_EPOCH,
    )

    hash_a = _sha256_numeric_fingerprint(out_a)
    hash_b = _sha256_numeric_fingerprint(out_b)

    print(f"\n[FP5-3] Run A SHA-256 = {hash_a}")
    print(f"[FP5-3] Run B SHA-256 = {hash_b}")

    assert len(hash_a) == 64, f"SHA-256 hash_a length unexpected: {len(hash_a)}"
    assert len(hash_b) == 64, f"SHA-256 hash_b length unexpected: {len(hash_b)}"
    assert hash_a == hash_b, (
        f"SHA-256 fingerprints differ between Run A and Run B!\n"
        f"  A: {hash_a}\n"
        f"  B: {hash_b}"
    )

    print(f"[FP5-3] PASS: SHA-256 fingerprints match — Feature Pipeline is reproducible.")


# ============================================================
# TEST 4 — FeaturePipeline.compute() direct determinism
# ============================================================

def test_fp5_4_pipeline_compute_direct_determinism() -> None:
    """FP-5 Requirement 4: FeaturePipeline.compute() called directly (bypassing
    the orchestrator timestamp injection layer) produces bit-identical DataFrames
    between two independent runs on the same input.

    This proves the transformer DAG itself is deterministic, independently of
    orchestrator-layer ND-1a/ND-1b. The FP-5 ND-1b fix is not needed at this
    layer — FeaturePipeline.compute() has zero datetime/random calls.
    """
    dep_graph = DependencyGraph()
    # Add nodes to the dependency graph using the correct DependencyGraph API
    for record in _FP5_FEATURE_RECORDS:
        dep_graph.add_node(record.name, record.dependencies)

    pipeline = FeaturePipeline(dep_graph)

    bars_df = _generate_synthetic_bars(num_bars=_NUM_BARS)

    # Run A — direct pipeline call
    out_a = pipeline.compute(names=_FP5_FEATURE_NAMES, input_df=bars_df.copy())

    # Run B — independent call, same input
    out_b = pipeline.compute(names=_FP5_FEATURE_NAMES, input_df=bars_df.copy())

    numeric_cols = sorted([c for c in out_a.columns if c not in _TIMESTAMP_COLUMNS])

    # Bit-identical equality — no tolerance
    pd.testing.assert_frame_equal(
        out_a[numeric_cols].reset_index(drop=True),
        out_b[numeric_cols].reset_index(drop=True),
        check_exact=True,
        check_names=True,
    )

    print(f"\n[FP5-4] PASS: FeaturePipeline.compute() is bit-identical between two "
          f"direct runs across {len(numeric_cols)} numeric columns × {len(out_a)} rows. "
          f"Transformer DAG is deterministic independently of orchestrator timestamps.")


# ============================================================
# TEST 5 — Warm-up edge determinism
# ============================================================

def test_fp5_5_warm_up_edge_determinism() -> None:
    """FP-5 Requirement 5: Early warm-up NaN/non-NaN positions are identical between
    Run A and Run B for ATR, RSI, EMA, and rolling calculations.

    Verifies that warm-up behavior is deterministic — both runs produce NaN
    in exactly the same positions during the initialisation period, and both
    produce non-NaN values at exactly the same positions after warm-up.

    Expected warm-up periods:
        ATR (window=14):         rows 0–13 → NaN
        RSI (window=14):         rows 0–13 → NaN
        EMA-9  (window=9):       rows 0–8  → NaN (pandas ewm default)
        EMA-21 (window=21):      rows 0–20 → NaN
        EMA-50 (window=50):      rows 0–49 → NaN
        rolling_std (window=20): rows 0–19 → NaN
    """
    orch_a = _build_orchestrator()
    out_a = orch_a.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=_generate_synthetic_bars().copy(),
        as_of_time=_FIXED_EPOCH,
    )

    orch_b = _build_orchestrator()
    out_b = orch_b.compute_and_store(
        names=_FP5_FEATURE_NAMES,
        symbol=_CANONICAL_SYMBOL,
        input_df=_generate_synthetic_bars().copy(),
        as_of_time=_FIXED_EPOCH,
    )

    # Warm-up sensitive features
    warm_up_features = ["atr", "rsi", "ema9", "ema21", "ema50", "rolling_std", "normalized_atr", "risk_score", "signal"]

    for feature in warm_up_features:
        assert feature in out_a.columns, f"Missing feature in Run A: {feature}"
        assert feature in out_b.columns, f"Missing feature in Run B: {feature}"

        nan_mask_a = out_a[feature].isna()
        nan_mask_b = out_b[feature].isna()

        # NaN positions must be identical between runs
        assert nan_mask_a.equals(nan_mask_b), (
            f"NaN positions differ for feature '{feature}' between Run A and Run B.\n"
            f"  A NaN count: {nan_mask_a.sum()}\n"
            f"  B NaN count: {nan_mask_b.sum()}"
        )

        # After warm-up, non-NaN values must be present (verify 500 bars is enough)
        non_nan_count = (~nan_mask_a).sum()
        assert non_nan_count > 0, (
            f"Feature '{feature}' has zero non-NaN values after 500 bars — "
            f"synthetic sequence may be too short."
        )

    # Print warm-up NaN summary for gate documentation
    print(f"\n[FP5-5] Warm-up NaN positions (Run A = Run B confirmed):")
    for feature in warm_up_features:
        nan_count = out_a[feature].isna().sum()
        print(f"  {feature:<18}: {nan_count:3d} NaN rows / {_NUM_BARS} total")

    print(f"[FP5-5] PASS: Warm-up edge NaN positions are identical between Run A and Run B.")
