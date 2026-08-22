"""Feature validation engine.
"""

from __future__ import annotations

import time
import uuid
import numpy as np
import pandas as pd

from research_platform.feature_platform.interfaces import IFeatureValidator
from research_platform.feature_platform.models import FeatureValidationResult


class FeatureValidator(IFeatureValidator):
    """Automatically audits feature data quality, lookahead leakage, stationarity, and PIT correctness."""

    def validate(self, name: str, df: pd.DataFrame) -> FeatureValidationResult:
        """Analyze a computed feature dataframe for data quality and leakage checks."""
        start_time = time.perf_counter()

        if name not in df.columns:
            raise KeyError(f"Feature column '{name}' not found in the DataFrame to validate.")

        series = df[name]
        total_rows = len(series)

        # 1. NaN and Missing ratios
        nan_count = series.isna().sum()
        nan_ratio = float(nan_count / total_rows) if total_rows > 0 else 1.0
        missing_ratio = nan_ratio

        # 2. Infinite values
        if pd.api.types.is_numeric_dtype(series):
            inf_count = int(np.isinf(series).sum())
        else:
            inf_count = 0

        # 3. PIT correctness check
        pit_passed = True
        if "as_of" in df.columns and "effective_time" in df.columns:
            # as_of must be >= effective_time
            as_of = pd.to_datetime(df["as_of"]).dt.tz_localize(None)
            eff = pd.to_datetime(df["effective_time"]).dt.tz_localize(None)
            if (as_of < eff).any():
                pit_passed = False

        # 4. Lookahead bias check
        has_lookahead = False
        if "timestamp" in df.columns:
            # Check if dataframe timestamps are non-decreasing
            times = pd.to_datetime(df["timestamp"])
            if not times.is_monotonic_increasing:
                has_lookahead = True
        if not pit_passed:
            has_lookahead = True

        # 5. Stationarity check (Heuristic: check mean and variance drift between halves)
        is_stationary = True
        valid_series = series.dropna()
        if pd.api.types.is_numeric_dtype(series) and len(valid_series) > 10:
            half = len(valid_series) // 2
            h1 = valid_series.iloc[:half]
            h2 = valid_series.iloc[half:]
            
            mean_diff = abs(h1.mean() - h2.mean())
            std_combined = valid_series.std()
            
            # If mean shifts by more than 1.5 combined standard deviations, flag non-stationarity
            if mean_diff > 1.5 * (std_combined + 1e-10):
                is_stationary = False
                
            # Compare variance ratio
            var1 = h1.var() + 1e-10
            var2 = h2.var() + 1e-10
            var_ratio = max(var1 / var2, var2 / var1)
            if var_ratio > 4.0:  # variance changed by over 4x
                is_stationary = False

        # 6. Multicollinearity/correlation check (correlation toClose if present)
        corr_score = 0.0
        if pd.api.types.is_numeric_dtype(series) and "close" in df.columns and len(valid_series) > 2:
            closes = df.loc[valid_series.index, "close"]
            corr_score = float(valid_series.corr(closes))
            if np.isnan(corr_score):
                corr_score = 0.0

        # Drift score
        drift_score = 0.0
        if pd.api.types.is_numeric_dtype(series) and len(valid_series) > 2:
            drift_score = float(valid_series.diff().std())

        # Performance footprints
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        memory_usage_mb = float(df.memory_usage(deep=True).sum() / (1024 * 1024))

        # Decision
        is_approved = (
            nan_ratio < 0.2 and 
            inf_count == 0 and 
            not has_lookahead and 
            pit_passed
        )

        return FeatureValidationResult(
            validation_id=str(uuid.uuid4()),
            feature_name=name,
            nan_ratio=nan_ratio,
            missing_ratio=missing_ratio,
            infinite_values_count=inf_count,
            has_lookahead_bias=has_lookahead,
            data_leakage_detected=has_lookahead,
            multicollinearity_score=abs(corr_score),
            is_stationary=is_stationary,
            drift_score=drift_score,
            latency_ms=latency_ms,
            memory_usage_mb=memory_usage_mb,
            pit_correctness_passed=pit_passed,
            is_approved=is_approved
        )
