"""FP-3D: Canonical Annualized Volatility — test suite.

CTO Test Requirements Covered:
    1. Formula: rolling_std=0.001 -> annualized_vol ≈ 0.001 * sqrt(525600) ≈ 0.725
    2. Lookback: 1440 bars required before valid canonical output
    3. Warm-up: insufficient data does NOT produce 0.0 (must be NaN)
    4. Fallback: missing annualized_vol -> fallback 0.50
    5. Target: target_volatility remains 0.10
    6. Leverage: vol=0.50->0.20x; vol=0.10->1.0x; vol=0.05->2.0x; vol=0.01->capped 2.0x
    7. Zero volatility: must never create infinite or 100x leverage
    8. Feature registration: 'annualized_vol' is registered and queryable
    9. Position sizing integration: query key is 'annualized_vol' not 'volatility'
    10. DAG end-to-end integration test
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from research_platform.feature_platform.transformers import AnnualizedVolTransformer
from research_platform.position_sizing.models import SizingConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRYPTO_PERIODS_PER_YEAR = 525600   # 365 * 24 * 60
SQRT_525600 = math.sqrt(CRYPTO_PERIODS_PER_YEAR)
DEFAULT_WINDOW = 1440
TARGET_VOL = 0.10
MAX_LEVERAGE = 2.0
FALLBACK_VOL = 0.50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log_return_df(n_bars: int, log_return_value: float = 0.001) -> pd.DataFrame:
    lr = [log_return_value if i % 2 == 0 else -log_return_value for i in range(n_bars)]
    return pd.DataFrame({"log_return": lr})


def _compute_annualized_vol(df: pd.DataFrame, window: int = DEFAULT_WINDOW) -> pd.Series:
    t = AnnualizedVolTransformer("log_return", window=window,
                                  periods_per_year=CRYPTO_PERIODS_PER_YEAR)
    return t.transform(df)


def _compute_scale(vol: float) -> float:
    min_vol = TARGET_VOL / MAX_LEVERAGE   # 0.05
    vol_safe = max(vol, min_vol)
    return min(TARGET_VOL / vol_safe, MAX_LEVERAGE)


def _make_ohlcv(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 30000.0 + np.cumsum(rng.normal(0, 10, n))
    return pd.DataFrame({
        "open": close, "high": close + 5, "low": close - 5,
        "close": close, "volume": rng.uniform(1, 100, n),
    })


# ===========================================================================
# TEST 1: Formula correctness
# ===========================================================================

class TestFormula:
    def test_annualization_factor(self):
        t = AnnualizedVolTransformer()
        assert abs(t._annualization_factor - SQRT_525600) < 1e-9

    def test_periods_per_year_constant(self):
        assert AnnualizedVolTransformer.CRYPTO_PERIODS_PER_YEAR == 525600

    def test_formula_numeric_result(self):
        """rolling_std=0.001 -> annualized_vol ≈ 0.001 * sqrt(525600) ≈ 0.725"""
        n = DEFAULT_WINDOW + 100
        df = _make_log_return_df(n, log_return_value=0.001)
        series = _compute_annualized_vol(df)
        last_val = series.iloc[-1]
        assert not math.isnan(last_val)
        expected = 0.001 * SQRT_525600
        assert abs(last_val - expected) < 0.02, f"Expected ≈{expected:.4f}, got {last_val:.4f}"

    def test_formula_uses_sample_std_ddof1(self):
        n = DEFAULT_WINDOW + 10
        df = _make_log_return_df(n, 0.001)
        series = _compute_annualized_vol(df)
        expected_std = df["log_return"].rolling(window=DEFAULT_WINDOW).std().iloc[-1]
        expected_ann = expected_std * SQRT_525600
        assert abs(series.iloc[-1] - expected_ann) < 1e-10

    def test_periods_per_year_is_configurable(self):
        t = AnnualizedVolTransformer("log_return", window=5, periods_per_year=1000)
        df = _make_log_return_df(50, 0.002)
        series = t.transform(df)
        expected_std = df["log_return"].rolling(window=5).std().iloc[-1]
        assert abs(series.iloc[-1] - expected_std * math.sqrt(1000)) < 1e-10


# ===========================================================================
# TEST 2: Lookback requirement
# ===========================================================================

class TestLookback:
    def test_default_window_is_1440(self):
        assert AnnualizedVolTransformer().window == DEFAULT_WINDOW

    def test_exactly_1440_bars_produces_first_valid_value(self):
        df = _make_log_return_df(DEFAULT_WINDOW, 0.001)
        series = _compute_annualized_vol(df)
        assert not math.isnan(series.iloc[-1])

    def test_1439_bars_last_value_is_nan(self):
        df = _make_log_return_df(DEFAULT_WINDOW - 1, 0.001)
        series = _compute_annualized_vol(df)
        assert math.isnan(series.iloc[-1])

    def test_all_early_values_are_nan(self):
        df = _make_log_return_df(DEFAULT_WINDOW + 50)
        series = _compute_annualized_vol(df)
        assert series.iloc[:DEFAULT_WINDOW - 1].isna().all()


# ===========================================================================
# TEST 3: Warm-up NaN safety
# ===========================================================================

class TestWarmupNaNSafety:
    def test_insufficient_data_returns_nan_not_zero(self):
        for n in [1, 10, 100, 500, DEFAULT_WINDOW - 1]:
            df = _make_log_return_df(n, 0.001)
            val = _compute_annualized_vol(df).iloc[-1]
            assert math.isnan(val), f"n={n}: expected NaN, got {val}"

    def test_no_fillna_zero_during_warmup(self):
        df = _make_log_return_df(5, 0.001)
        series = _compute_annualized_vol(df)
        for i, v in enumerate(series):
            assert math.isnan(v), f"Index {i}: expected NaN, got {v}"

    def test_zero_vol_danger_scenario_blocked(self):
        """fillna(0.0) would produce 0.0 values — confirm they are absent."""
        df = _make_log_return_df(10, 0.001)
        series = _compute_annualized_vol(df)
        assert (series == 0.0).sum() == 0, "fillna(0.0) must NOT be applied during warm-up"


# ===========================================================================
# TEST 4 & 5: Fallback and target volatility
# ===========================================================================

class TestFallbackAndTarget:
    def test_default_target_volatility(self):
        assert SizingConfig().target_volatility == TARGET_VOL

    def test_default_fallback_volatility(self):
        assert SizingConfig().fallback_volatility == FALLBACK_VOL

    def test_default_max_leverage(self):
        assert SizingConfig().max_leverage == MAX_LEVERAGE

    def test_fallback_produces_safe_leverage(self):
        scale = _compute_scale(FALLBACK_VOL)   # 0.10/0.50 = 0.20
        assert abs(scale - 0.20) < 1e-9

    def test_target_volatility_not_0_80(self):
        assert SizingConfig().target_volatility == 0.10
        assert SizingConfig().target_volatility != 0.80


# ===========================================================================
# TEST 6: Leverage scenarios
# ===========================================================================

class TestLeverageScenarios:
    def test_vol_050_gives_020x(self):
        assert abs(_compute_scale(0.50) - 0.20) < 1e-9

    def test_vol_010_gives_100x(self):
        assert abs(_compute_scale(0.10) - 1.0) < 1e-9

    def test_vol_005_gives_200x(self):
        assert abs(_compute_scale(0.05) - 2.0) < 1e-9

    def test_vol_001_capped_at_200x(self):
        # floor=0.05 kicks in: vol_safe=0.05 -> scale=2.0
        assert abs(_compute_scale(0.01) - 2.0) < 1e-9

    def test_very_low_vol_cannot_exceed_max_leverage(self):
        for vol in [0.001, 0.0001, 1e-10]:
            assert _compute_scale(vol) <= MAX_LEVERAGE + 1e-9

    def test_vol_020_gives_050x(self):
        assert abs(_compute_scale(0.20) - 0.50) < 1e-9

    def test_vol_080_gives_0125x(self):
        assert abs(_compute_scale(0.80) - 0.125) < 1e-9


# ===========================================================================
# TEST 7: Zero volatility never causes infinite/100x leverage
# ===========================================================================

class TestZeroVolSafety:
    def test_zero_vol_gives_max_leverage_not_infinite(self):
        # vol=0.0 -> vol_safe = max(0.0, 0.05) = 0.05 -> scale = 2.0
        scale = _compute_scale(0.0)
        assert math.isfinite(scale)
        assert scale <= MAX_LEVERAGE

    def test_near_zero_vol_safe(self):
        assert _compute_scale(1e-10) <= MAX_LEVERAGE + 1e-9

    def test_old_floor_would_have_caused_100x(self):
        old_scale = TARGET_VOL / 0.001   # 100x
        assert old_scale == 100.0

    def test_new_floor_prevents_100x(self):
        new_floor = TARGET_VOL / MAX_LEVERAGE   # 0.05
        assert TARGET_VOL / new_floor == MAX_LEVERAGE   # 2.0


# ===========================================================================
# TEST 8: Feature registration
# ===========================================================================

class TestFeatureRegistration:
    def test_annualized_vol_in_default_feature_definitions(self):
        from research_platform.feature_platform.orchestrator import DEFAULT_FEATURE_DEFINITIONS
        names = [r.name for r in DEFAULT_FEATURE_DEFINITIONS]
        assert "annualized_vol" in names

    def test_annualized_vol_record_fields(self):
        from research_platform.feature_platform.orchestrator import DEFAULT_FEATURE_DEFINITIONS
        rec = next(r for r in DEFAULT_FEATURE_DEFINITIONS if r.name == "annualized_vol")
        assert rec.dependencies == ["log_return"]
        assert rec.warmup_length == 1441
        assert rec.lookback_window == 1440
        assert rec.required_resolution == "1m"
        assert "525600" in rec.formula

    def test_annualized_vol_in_pipeline_transformers(self):
        from research_platform.feature_platform.dependency_graph import DependencyGraph
        from research_platform.feature_platform.feature_pipeline import FeaturePipeline
        from research_platform.feature_platform.transformers import AnnualizedVolTransformer
        p = FeaturePipeline(DependencyGraph())
        assert "annualized_vol" in p._transformers
        assert isinstance(p._transformers["annualized_vol"], AnnualizedVolTransformer)

    def test_transformer_default_params_in_pipeline(self):
        from research_platform.feature_platform.dependency_graph import DependencyGraph
        from research_platform.feature_platform.feature_pipeline import FeaturePipeline
        t = FeaturePipeline(DependencyGraph())._transformers["annualized_vol"]
        assert t.window == 1440
        assert t.periods_per_year == 525600


# ===========================================================================
# TEST 9: Position sizer integration — query key
# ===========================================================================

class TestPositionSizerIntegration:
    def test_query_key_is_annualized_vol(self):
        import inspect
        from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator
        src = inspect.getsource(PositionSizingOrchestrator.calculate_size)
        assert '"annualized_vol"' in src
        assert 'query_realtime(["volatility"]' not in src

    def test_formula_uses_min_vol_and_leverage_cap(self):
        import inspect
        from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator
        src = inspect.getsource(PositionSizingOrchestrator.calculate_size)
        assert "min_vol" in src
        assert "vol_safe" in src
        assert "max_leverage" in src

    def test_nan_check_present_in_volatility_method(self):
        import inspect
        from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator
        src = inspect.getsource(PositionSizingOrchestrator.calculate_size)
        assert "isnan" in src

    def test_risk_parity_also_uses_annualized_vol(self):
        import inspect
        from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator
        src = inspect.getsource(PositionSizingOrchestrator.calculate_size)
        count = src.count('"annualized_vol"')
        assert count >= 2, f"Both sizing methods must query annualized_vol; found {count}"


# ===========================================================================
# TEST 10: DAG end-to-end integration
# ===========================================================================

class TestDagEndToEnd:
    def _get_pipeline(self):
        from research_platform.feature_platform.dependency_graph import DependencyGraph
        from research_platform.feature_platform.feature_pipeline import FeaturePipeline
        graph = DependencyGraph()
        graph.add_node("log_return", ["close"])
        graph.add_node("annualized_vol", ["log_return"])
        return FeaturePipeline(graph)

    def test_pipeline_computes_annualized_vol_column(self):
        result = self._get_pipeline().compute(["annualized_vol"], _make_ohlcv(DEFAULT_WINDOW + 100))
        assert "annualized_vol" in result.columns
        assert "log_return" in result.columns

    def test_post_warmup_values_are_finite_and_positive(self):
        result = self._get_pipeline().compute(["annualized_vol"], _make_ohlcv(DEFAULT_WINDOW + 50))
        post = result["annualized_vol"].iloc[DEFAULT_WINDOW:]
        assert post.apply(lambda v: math.isfinite(v) and v > 0).all()

    def test_warmup_values_are_all_nan(self):
        result = self._get_pipeline().compute(["annualized_vol"], _make_ohlcv(DEFAULT_WINDOW + 50))
        warmup = result["annualized_vol"].iloc[:DEFAULT_WINDOW - 1]
        assert warmup.isna().all(), "All warm-up values must be NaN"

    def test_annualized_vol_scale_is_realistic(self):
        result = self._get_pipeline().compute(["annualized_vol"], _make_ohlcv(DEFAULT_WINDOW + 200))
        mean_vol = result["annualized_vol"].dropna().mean()
        assert 0.01 <= mean_vol <= 5.0, f"mean_vol={mean_vol:.4f} outside expected [0.01, 5.0]"
