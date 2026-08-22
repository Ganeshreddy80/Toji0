"""Walk Forward Testing and overfitting detection engine.
"""

from __future__ import annotations
import pandas as pd
from typing import Dict, Any

from research_platform.strategy_factory.models import StrategyCandidate
from research_platform.strategy_factory.evaluator import StrategyEvaluator

class WalkForwardOptimizer:
    """Splits data into training/test phases and evaluates out-of-sample performance."""

    def __init__(self, evaluator: StrategyEvaluator) -> None:
        self.evaluator = evaluator

    def optimize_and_validate(
        self,
        candidate: StrategyCandidate,
        data_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Split historical data, evaluate candidate on in-sample and out-of-sample segments."""
        if "timestamp" not in data_df.columns:
            data_df["timestamp"] = pd.date_range(start="2020-01-01", periods=len(data_df), freq="h")
            
        data_df["timestamp"] = pd.to_datetime(data_df["timestamp"])
        
        # Split: Training 2019-2023 vs Test 2024 (unseen)
        train_df = data_df[data_df["timestamp"] < pd.Timestamp("2024-01-01")].copy()
        test_df = data_df[data_df["timestamp"] >= pd.Timestamp("2024-01-01")].copy()

        # Fallback if splits are too small/empty
        if train_df.empty:
            train_df = data_df.iloc[:len(data_df)//2].copy()
            test_df = data_df.iloc[len(data_df)//2:].copy()

        # Score both segments
        train_score = self.evaluator.evaluate_strategy(candidate, train_df)
        test_score = self.evaluator.evaluate_strategy(candidate, test_df)

        # Detect Overfitting
        # If strategy performed well in training but completely failed in unseen testing
        overfitting = False
        if train_score.score >= 70.0 and test_score.score < 50.0:
            overfitting = True

        # Reject strategies if overfitted or test score is poor
        rejected = overfitting or (test_score.score < 55.0)

        return {
            "strategy": candidate.name,
            "train_score": train_score.score,
            "test_score": test_score.score,
            "overfitting": overfitting,
            "rejected": rejected
        }
