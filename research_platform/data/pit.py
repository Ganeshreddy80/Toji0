"""PointInTimeDataManager module to manage historical queries and prevent lookahead bias.
"""

from __future__ import annotations

import pandas as pd
from typing import List


class PointInTimeDataManager:
    """Performs point-in-time data joins, ensuring features are aligned exactly when they became known."""

    @staticmethod
    def align_features(
        observations: pd.DataFrame,
        features: pd.DataFrame,
        on_key: str = "symbol"
    ) -> pd.DataFrame:
        """Align features with market observations point-in-time.

        Args:
            observations: DataFrame containing 'timestamp', 'symbol', and price info.
            features: DataFrame containing 'effective_time', 'as_of', 'symbol', and feature columns.
            on_key: Column key to join on (usually 'symbol').

        Returns:
            DataFrame containing observations joined with PIT aligned features.
        """
        obs = observations.copy()
        obs["timestamp"] = pd.to_datetime(obs["timestamp"])

        feats = features.copy()
        feats["effective_time"] = pd.to_datetime(feats["effective_time"])
        feats["as_of"] = pd.to_datetime(feats["as_of"])

        # Sort values to support merge_asof
        obs.sort_values("timestamp", inplace=True)
        feats.sort_values("as_of", inplace=True)

        # Perform merge_asof grouped by symbol
        aligned = pd.merge_asof(
            obs,
            feats,
            left_on="timestamp",
            right_on="as_of",
            by=on_key,
            direction="backward"  # only pick feature rows where as_of <= timestamp
        )

        return aligned
