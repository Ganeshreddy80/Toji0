"""Feature Importance Framework.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

from research_platform.feature_platform.interfaces import IImportanceFramework
from research_platform.feature_platform.models import FeatureImportanceMetrics


class ImportanceFramework(IImportanceFramework):
    """Computes Mutual Information (MI), Information Coefficients (IC), and Information Ratios (IR)."""

    def compute_importance(
        self,
        feature_name: str,
        values: pd.Series,
        returns: pd.Series
    ) -> FeatureImportanceMetrics:
        """Compute Mutual Information, IC, and IR metrics."""
        # Align indexes
        df = pd.concat([values, returns], axis=1).dropna()
        df.columns = ["x", "y"]
        
        if len(df) < 5:
            # Not enough samples for correlation
            return FeatureImportanceMetrics(
                feature_name=feature_name,
                target_name=returns.name or "returns",
                mutual_information=0.0,
                information_coefficient=0.0,
                information_ratio=0.0,
                permutation_importance=0.0,
                feature_rank=99
            )

        X = df["x"].values
        Y = df["y"].values

        # 1. Compute Information Coefficient (Pearson Correlation)
        ic = float(np.corrcoef(X, Y)[0, 1])
        if np.isnan(ic):
            ic = 0.0

        # 2. Compute Mutual Information natively via binning
        mi = self._calculate_mutual_information(X, Y)

        # 3. Compute Information Ratio (rolling/sample heuristic: mean return scale over std)
        # For a single series correlation, we can estimate IR = IC * sqrt(N)
        ir = ic * math.sqrt(len(df))

        return FeatureImportanceMetrics(
            feature_name=feature_name,
            target_name=returns.name or "returns",
            mutual_information=mi,
            information_coefficient=ic,
            information_ratio=ir,
            permutation_importance=0.0,  # can be populated in model runs
            feature_rank=1
        )

    def _calculate_mutual_information(self, X: np.ndarray, Y: np.ndarray, bins: int = 10) -> float:
        """Calculate Mutual Information score natively using 2D histogram binning."""
        try:
            # 2D joint histogram
            joint_hist, _, _ = np.histogram2d(X, Y, bins=bins)
            total = np.sum(joint_hist)
            if total == 0:
                return 0.0

            p_xy = joint_hist / total
            
            # Marginals
            p_x = np.sum(p_xy, axis=1, keepdims=True)
            p_y = np.sum(p_xy, axis=0, keepdims=True)
            
            # MI calculation: sum p(x,y) * log( p(x,y) / (p(x)*p(y)) )
            mi = 0.0
            for i in range(bins):
                for j in range(bins):
                    pxy = p_xy[i, j]
                    px = p_x[i, 0]
                    py = p_y[0, j]
                    if pxy > 0 and px > 0 and py > 0:
                        mi += pxy * math.log(pxy / (px * py))
            return max(mi, 0.0)
        except Exception:
            return 0.0
