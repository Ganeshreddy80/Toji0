"""Feature Orthogonalization checker.
"""

from __future__ import annotations

from typing import Dict, List
import pandas as pd

from research_platform.feature_platform.interfaces import IOrthogonalizer
from research_platform.feature_platform.models import OrthogonalizationReport


class Orthogonalizer(IOrthogonalizer):
    """Analyzes multicollinearity, overlaps, and redundancy across calculated feature sets."""

    def analyze_orthogonal(self, name: str, df: pd.DataFrame, threshold: float = 0.85) -> OrthogonalizationReport:
        """Compare correlation with existing dataframe columns and recommend actions."""
        if name not in df.columns:
            raise KeyError(f"Feature '{name}' not found in the DataFrame.")

        collinear_features: Dict[str, float] = {}
        redundant_features: List[str] = []
        max_corr = 0.0

        series = df[name]
        
        # Calculate correlation with other columns
        for col in df.columns:
            if col == name or col in ("timestamp", "symbol", "effective_time", "as_of"):
                continue
            
            # Skip non-numeric columns
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue
                
            try:
                corr = float(series.corr(df[col]))
                if pd.isna(corr):
                    corr = 0.0
                
                abs_corr = abs(corr)
                if abs_corr > max_corr:
                    max_corr = abs_corr
                
                if abs_corr > threshold:
                    collinear_features[col] = corr
                    redundant_features.append(col)
            except Exception:
                continue

        # Recommend Action
        if max_corr > 0.90:
            recommended_action = "REMOVE_REDUNDANT"
        elif max_corr > threshold:
            recommended_action = "GROUP_OR_ORTHOGONALIZE"
        else:
            recommended_action = "APPROVE"

        # Determine overlap grouping based on maximum correlation column
        overlap_group = "orthogonal"
        if redundant_features:
            # find largest corr column name
            largest_col = max(collinear_features, key=lambda k: abs(collinear_features[k]))
            overlap_group = f"group_{largest_col}"

        return OrthogonalizationReport(
            feature_name=name,
            collinear_features=collinear_features,
            redundant_features=redundant_features,
            maximum_correlation=max_corr,
            overlap_group=overlap_group,
            recommended_action=recommended_action
        )
