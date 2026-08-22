"""Vectorized mathematical operators for the Alpha DSL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rank(x: pd.Series) -> pd.Series:
    """Compute rolling or series-wide rank normalized between 0.0 and 1.0."""
    return x.rank(pct=True)


def ts_mean(x: pd.Series, n: int) -> pd.Series:
    """Compute rolling mean over a period of n days."""
    return x.rolling(window=max(n, 1), min_periods=1).mean()


def delta(x: pd.Series, n: int) -> pd.Series:
    """Compute difference: x - x.shift(n)."""
    return x.diff(periods=max(n, 1))


def correlation(x: pd.Series, y: pd.Series, n: int) -> pd.Series:
    """Compute rolling correlation over window n."""
    return x.rolling(window=max(n, 1), min_periods=2).corr(y)


def ts_rank(x: pd.Series, n: int) -> pd.Series:
    """Compute rolling rank of value compared to historical window n."""
    def rank_func(w):
        if len(w) == 0:
            return 0.5
        last = w[-1]
        return float(np.sum(w < last) / len(w))
    return x.rolling(window=max(n, 1), min_periods=1).apply(rank_func, raw=True)


def signed_power(x: pd.Series, y: float) -> pd.Series:
    """Compute sign(x) * |x|^y."""
    return np.sign(x) * (x.abs() ** y)


def decay_linear(x: pd.Series, n: int) -> pd.Series:
    """Compute linearly decaying weighted moving average over period n."""
    n = max(n, 1)
    weights = np.arange(1, n + 1)
    weights = weights / weights.sum()
    
    def decay_func(w):
        if len(w) < n:
            # fallback for shorter windows
            sub_w = weights[-len(w):]
            sub_w = sub_w / sub_w.sum()
            return float(np.sum(w * sub_w))
        return float(np.sum(w * weights))

    return x.rolling(window=n, min_periods=1).apply(decay_func, raw=True)


def adv20(volume: pd.Series) -> pd.Series:
    """Compute 20-day Average Daily Volume."""
    return ts_mean(volume, 20)


def rolling_zscore(x: pd.Series, n: int) -> pd.Series:
    """Compute rolling z-score: (x - mean) / std."""
    n = max(n, 2)
    mean = x.rolling(window=n, min_periods=1).mean()
    std = x.rolling(window=n, min_periods=1).std(ddof=1)
    return (x - mean) / (std + 1e-10)


def neutralize(x: pd.Series, groups: pd.Series) -> pd.Series:
    """De-means the target series within categories/groups to remove factor exposure."""
    df = pd.DataFrame({"x": x, "group": groups})
    # Compute mean by group and subtract
    group_means = df.groupby("group")["x"].transform("mean")
    return x - group_means


def cross_sectional_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Ranks values cross-sectionally across columns for each timestamp row."""
    return df.rank(axis=1, pct=True)
