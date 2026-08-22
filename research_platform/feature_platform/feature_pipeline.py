"""Feature Pipeline DAG executor.
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, List, Any

from research_platform.feature_platform.interfaces import IFeaturePipeline
from research_platform.feature_platform.dependency_graph import DependencyGraph
from research_platform.feature_platform.transformers import (
    AnnualizedVolTransformer,
    AtrTransformer,
    BreakoutTransformer,
    CloseTransformer,
    EmaTransformer,
    HighTransformer,
    LogReturnTransformer,
    LowTransformer,
    NormalizedAtrTransformer,
    OpenTransformer,
    ResistanceTransformer,
    RiskScoreTransformer,
    RollingStdTransformer,
    RsiTransformer,
    SignalTransformer,
    SupportTransformer,
    TrendDirectionTransformer,
    VolumeChangeTransformer,
    VolumeTransformer,
)


class FeaturePipeline(IFeaturePipeline):
    """Orchestrates sequential, cached executions of a feature dependency DAG."""

    def __init__(self, dep_graph: DependencyGraph) -> None:
        self._graph = dep_graph
        # Registry mapping technical feature names to their transformer steps
        self._transformers: Dict[str, Any] = {
            "close": CloseTransformer(),
            "log_return": LogReturnTransformer("close"),
            "rolling_std": RollingStdTransformer("log_return", window=20),
            # FP-3D: Canonical annualized realized volatility for position sizing.
            # window=1440 (1 day of 1-minute bars), periods_per_year=525600 (crypto 24/7).
            # NaN during warm-up — position sizer uses fallback_volatility (0.50) instead.
            "annualized_vol": AnnualizedVolTransformer("log_return", window=1440, periods_per_year=525600),
            "atr": AtrTransformer(window=14),
            "normalized_atr": NormalizedAtrTransformer("atr", "close"),
            "risk_score": RiskScoreTransformer("normalized_atr", window=50),
            "signal": SignalTransformer("risk_score", threshold=2.0),
            "open": OpenTransformer(),
            "high": HighTransformer(),
            "low": LowTransformer(),
            "volume": VolumeTransformer(),
            "ema9": EmaTransformer("close", window=9),
            "ema21": EmaTransformer("close", window=21),
            "ema50": EmaTransformer("close", window=50),
            "rsi": RsiTransformer("close", window=14),
            "volume_change": VolumeChangeTransformer(),
            "support": SupportTransformer(window=20),
            "resistance": ResistanceTransformer(window=20),
            "breakout": BreakoutTransformer(),
            "trend": TrendDirectionTransformer(),
        }

    def compute(self, names: List[str], input_df: pd.DataFrame) -> pd.DataFrame:
        """Compute target features in dependency order, caching calculations.

        Args:
            names: List of features to calculate.
            input_df: DataFrame containing raw price columns ('close', 'high', 'low').

        Returns:
            DataFrame with computed feature columns appended.
        """
        df = input_df.copy()
        
        # Get execution plan (topologically sorted path)
        plan = self._graph.get_execution_plan(names)
        
        # Sequentially execute transformers
        for node in plan:
            if node in df.columns:
                # Already cached/computed in input
                continue
                
            transformer = self._transformers.get(node)
            if transformer is None:
                raise KeyError(
                    f"No registered transformer definition found for feature '{node}' in pipeline registry."
                )
            
            # Execute calculation step
            series = transformer.transform(df)
            df[node] = series

        return df
