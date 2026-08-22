"""Data Quality Engine executing missing values, duplicate checks, and drifts.
"""

from __future__ import annotations

import uuid
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any

from research_platform.data_platform.interfaces import IDataQualityEngine
from research_platform.data_platform.models import DataQualityReport


class DataQualityEngine(IDataQualityEngine):
    """Executes validation gates checks and computes dataset quality metrics."""

    def evaluate_quality(self, version_id: str, df: pd.DataFrame) -> DataQualityReport:
        """Run validation checks and compute dataset quality scores.

        Deducts penalty parameters for missing cells and duplicate rows.
        """
        if df.empty:
            return DataQualityReport(
                report_id=str(uuid.uuid4()),
                dataset_version_id=version_id,
                score=0.0,
                missing_pct=1.0,
                duplicates_count=0,
                drift_status="UNSTABLE"
            )

        # 1. Missing values
        total_cells = df.size
        missing_count = int(df.isna().sum().sum())
        missing_pct = float(missing_count / total_cells)

        # 2. Duplicate rows
        dup_count = int(df.duplicated().sum())
        duplicate_pct = float(dup_count / len(df))

        # 3. Quality score calculation
        # Deduct penalties for missing rates and duplicate percentages
        score = max(0.0, 1.0 - (missing_pct * 2.0 + duplicate_pct))

        # 4. Outlier value validation (e.g. checking close prices <= 0)
        drift_status = "STABLE"
        if "close" in df.columns:
            invalid_prices = df[df["close"] <= 0.0]
            if not invalid_prices.empty:
                drift_status = "INVALID_VALUES"
                score = max(0.0, score - 0.5)

        return DataQualityReport(
            report_id=str(uuid.uuid4()),
            dataset_version_id=version_id,
            score=score,
            missing_pct=missing_pct,
            duplicates_count=dup_count,
            drift_status=drift_status,
            timestamp=datetime.now(timezone.utc)
        )

    @staticmethod
    def detect_distribution_drift(
        base_series: pd.Series,
        target_series: pd.Series,
        threshold_std: float = 2.0
    ) -> bool:
        """Detect statistical drift between two historical data windows.

        Triggers True if difference in means exceeds standard deviation bounds.
        """
        mean_base = float(base_series.mean())
        std_base = float(base_series.std())
        mean_target = float(target_series.mean())

        if std_base == 0.0:
            return mean_base != mean_target

        drift = abs(mean_base - mean_target) / std_base
        return drift > threshold_std
