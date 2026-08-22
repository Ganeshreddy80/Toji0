"""Research datasets generation, splitting, and series windowing utilities."""

from __future__ import annotations

import pandas as pd


class DatasetGenerator:
    """Helper to partition historical series dataframes for backtesting and ML."""

    @staticmethod
    def train_test_split(
        df: pd.DataFrame, ratio: float = 0.8
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Perform sequential (time-series safe) train-test split."""
        if df.empty:
            return df, df
        split_idx = int(len(df) * ratio)
        return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()

    @staticmethod
    def generate_rolling_windows(
        df: pd.DataFrame, window_size: int, step: int = 1
    ) -> list[pd.DataFrame]:
        """Generate rolling sequence slices of window_size records."""
        windows: list[pd.DataFrame] = []
        if len(df) < window_size:
            return windows
        for i in range(0, len(df) - window_size + 1, step):
            windows.append(df.iloc[i : i + window_size].copy())
        return windows
