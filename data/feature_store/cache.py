"""In-memory cache implementing IFeatureStore to store computed feature dataframes."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import TYPE_CHECKING

from data.feature_store.interfaces import IFeatureStore

if TYPE_CHECKING:
    import pandas as pd


class FeatureCache(IFeatureStore):
    """In-memory thread-safe cache for computed features dataframes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Key: (symbol, feature_name, version) -> DataFrame
        self._cache: dict[tuple[str, str, str], pd.DataFrame] = {}

    def get_features(
        self,
        symbol: str,
        features: list[tuple[str, str]],
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Combine cached features over date range into one DataFrame.

        If any feature is missing, it returns an empty DataFrame or handles merge.
        """
        import pandas as pd

        with self._lock:
            dfs: list[pd.DataFrame] = []
            for name, version in features:
                key = (symbol.upper(), name.upper(), version)
                if key in self._cache:
                    df = self._cache[key]
                    # Filter by date range (assuming index is DatetimeIndex)
                    if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                        filtered = df.loc[start:end]  # type: ignore[misc]
                        dfs.append(filtered)
                    else:
                        dfs.append(df)

            if not dfs:
                return pd.DataFrame()

            # Merge all dataframes on index (timestamp)
            result = dfs[0]
            for next_df in dfs[1:]:
                # Outer join to align timestamps
                result = result.join(next_df, how="outer", rsuffix="_dup")

            return result

    def save_features(
        self,
        symbol: str,
        feature_name: str,
        version: str,
        data: pd.DataFrame,
    ) -> None:
        """Save computed feature DataFrame into cache."""
        key = (symbol.upper(), feature_name.upper(), version)
        with self._lock:
            # We copy the dataframe to prevent external modification issues
            self._cache[key] = data.copy()

    def clear(self) -> None:
        """Clear all cached features."""
        with self._lock:
            self._cache.clear()
