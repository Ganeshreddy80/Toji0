"""Data Quality Analyzer for running structural, schema, and integrity validation rules."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


class QualityCheckResult(BaseModel):
    """Validation outcome report."""

    passed: bool = Field(..., description="True if no errors were found")
    errors: list[str] = Field(default_factory=list, description="List of quality error messages")
    metrics: dict[str, float] = Field(
        default_factory=dict, description="Key metrics (e.g. missing_rate, duplicate_count)"
    )

    model_config = {"frozen": True}


class DataQualityAnalyzer:
    """Validator for verifying data shapes, structures, ordering, and schemas."""

    def validate_schema(self, data: list[dict] | pd.DataFrame, model_cls: type[BaseModel]) -> QualityCheckResult:
        """Validate row/item dictionary list against a canonical Pydantic schema."""
        errors: list[str] = []
        rows = data if isinstance(data, list) else data.to_dict(orient="records")

        for idx, row in enumerate(rows):
            try:
                model_cls(**row)
            except Exception as e:
                errors.append(f"Row {idx} schema violation: {e}")

        passed = len(errors) == 0
        return QualityCheckResult(passed=passed, errors=errors)

    def check_missing(self, df: pd.DataFrame, expected_interval: str) -> QualityCheckResult:
        """Check for gap intervals in DatetimeIndex."""
        errors: list[str] = []
        metrics: dict[str, float] = {"missing_count": 0.0, "missing_rate": 0.0}

        if df.empty:
            return QualityCheckResult(passed=True, errors=errors, metrics=metrics)

        if not isinstance(df.index, pd.DatetimeIndex):
            return QualityCheckResult(
                passed=False,
                errors=["DataFrame index is not a DatetimeIndex; cannot check missing intervals."],
                metrics=metrics,
            )

        # Map interval codes to pandas frequency codes
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
        }
        freq = freq_map.get(expected_interval.lower(), expected_interval)

        # Generate expected index range
        try:
            expected_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
        except Exception as e:
            return QualityCheckResult(
                passed=False,
                errors=[f"Failed to generate expected date range for frequency '{freq}': {e}"],
                metrics=metrics,
            )

        missing = expected_index.difference(df.index)
        missing_count = len(missing)
        total_expected = len(expected_index)

        metrics["missing_count"] = float(missing_count)
        metrics["missing_rate"] = float(missing_count / total_expected) if total_expected > 0 else 0.0

        if missing_count > 0:
            errors.append(
                f"Detected {missing_count} missing intervals (e.g. {list(missing[:3])}) out of {total_expected} expected."
            )

        return QualityCheckResult(passed=len(errors) == 0, errors=errors, metrics=metrics)

    def check_duplicates(self, df: pd.DataFrame, key_cols: list[str] | None = None) -> QualityCheckResult:
        """Identify duplicate records based on either DatetimeIndex or subset columns."""
        errors: list[str] = []
        metrics: dict[str, float] = {"duplicate_count": 0.0}

        if df.empty:
            return QualityCheckResult(passed=True, errors=errors, metrics=metrics)

        # Find duplicates
        if key_cols:
            duplicates = df.duplicated(subset=key_cols, keep="first")
        else:
            if isinstance(df.index, pd.DatetimeIndex):
                # Check index duplicates
                duplicates = df.index.duplicated(keep="first")
            else:
                duplicates = df.duplicated(keep="first")

        duplicate_count = int(duplicates.sum())
        metrics["duplicate_count"] = float(duplicate_count)

        if duplicate_count > 0:
            errors.append(f"Found {duplicate_count} duplicate records.")

        return QualityCheckResult(passed=len(errors) == 0, errors=errors, metrics=metrics)

    def check_ordering(self, df: pd.DataFrame) -> QualityCheckResult:
        """Verify index timestamps are strictly monotonically increasing."""
        errors: list[str] = []

        if df.empty:
            return QualityCheckResult(passed=True, errors=errors)

        is_monotonic = df.index.is_monotonic_increasing
        if not is_monotonic:
            errors.append("DataFrame index timestamps are not strictly monotonically increasing.")

        return QualityCheckResult(passed=is_monotonic, errors=errors)

    def check_integrity(self, df: pd.DataFrame) -> QualityCheckResult:
        """Validate logical boundary constraints for OHLCV bars."""
        errors: list[str] = []

        if df.empty:
            return QualityCheckResult(passed=True, errors=errors)

        required = {"open", "high", "low", "close"}
        if not required.issubset(df.columns):
            return QualityCheckResult(
                passed=True,
                errors=["Columns do not contain OHLC; skipping integrity checks."],
            )

        # Check bounds
        high_low_viol = df[df["high"] < df["low"]]
        if not high_low_viol.empty:
            errors.append(f"High price is below Low price in {len(high_low_viol)} rows.")

        high_open_viol = df[df["high"] < df["open"]]
        if not high_open_viol.empty:
            errors.append(f"High price is below Open price in {len(high_open_viol)} rows.")

        high_close_viol = df[df["high"] < df["close"]]
        if not high_close_viol.empty:
            errors.append(f"High price is below Close price in {len(high_close_viol)} rows.")

        low_open_viol = df[df["low"] > df["open"]]
        if not low_open_viol.empty:
            errors.append(f"Low price is above Open price in {len(low_open_viol)} rows.")

        low_close_viol = df[df["low"] > df["close"]]
        if not low_close_viol.empty:
            errors.append(f"Low price is above Close price in {len(low_close_viol)} rows.")

        if "volume" in df.columns:
            neg_vol = df[df["volume"] < 0]
            if not neg_vol.empty:
                errors.append(f"Volume is negative in {len(neg_vol)} rows.")

        for col in ["open", "high", "low", "close"]:
            neg_vals = df[df[col] <= 0]
            if not neg_vals.empty:
                errors.append(f"{col.capitalize()} price is non-positive in {len(neg_vals)} rows.")

        return QualityCheckResult(passed=len(errors) == 0, errors=errors)
