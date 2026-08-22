"""Point-In-Time Feature Store implementation.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd

from research_platform.data.pit import PointInTimeDataManager
from research_platform.feature_platform.interfaces import IFeatureStore


def _parse_semver(version: str) -> Tuple[int, int, int]:
    """Parse a strict 'major.minor.patch' version string into an integer tuple.

    Raises ValueError for malformed version strings.
    """
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Malformed semantic version '{version}': expected exactly 3 dot-separated parts.")
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        raise ValueError(f"Malformed semantic version '{version}': all parts must be integers.")


class FeatureStore(IFeatureStore):
    """Point-in-Time Offline and Online Store for versioned quantitative features."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Storage schema: (feature_name, version, symbol) -> pd.DataFrame
        self._offline_db: Dict[Tuple[str, str, str], pd.DataFrame] = {}
        self._online_db: Dict[Tuple[str, str, str], pd.DataFrame] = {}

    def save_features(self, name: str, version: str, symbol: str, df: pd.DataFrame) -> None:
        """Save computed feature values for a symbol.

        df should contain columns: 'effective_time', 'as_of', and the feature values.
        """
        # Ensure PIT columns exist
        cols = df.columns
        if "effective_time" not in cols or "as_of" not in cols:
            raise KeyError("DataFrame must contain 'effective_time' and 'as_of' columns for PIT storage.")

        with self._lock:
            key = (name, version, symbol)
            self._offline_db[key] = df.copy()
            # Online stores just the latest values for streaming/live
            if len(df) > 0:
                self._online_db[key] = df.sort_values("as_of").tail(1)

    def query_historical(
        self,
        names: List[str],
        symbols: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> pd.DataFrame:
        """Perform time-travel Point-In-Time query over historical dates."""
        results = []
        with self._lock:
            for symbol in symbols:
                # Base observation timeline
                times = pd.date_range(start_time, end_time, freq="1min")
                obs_df = pd.DataFrame({
                    "timestamp": times,
                    "symbol": symbol
                })
                
                # Align each feature onto observations
                merged = obs_df
                for name in names:
                    # Let's search for the latest version key
                    matching_keys = [k for k in self._offline_db.keys() if k[0] == name and k[2] == symbol]
                    if not matching_keys:
                        continue
                    
                    # Sort keys to pick latest version using semantic version comparison
                    latest_key = sorted(matching_keys, key=lambda k: _parse_semver(k[1]))[-1]
                    feature_df = self._offline_db[latest_key]

                    # PIT alignment join
                    merged = PointInTimeDataManager.align_features(
                        merged,
                        feature_df[[name, "effective_time", "as_of", "symbol"]],
                        on_key="symbol"
                    )
                results.append(merged)

        if not results:
            return pd.DataFrame()
        return pd.concat(results, ignore_index=True)

    def query_latest(self, names: List[str], symbols: List[str]) -> pd.DataFrame:
        """Fetch latest computed feature states for stream/live executions."""
        rows = []
        with self._lock:
            for symbol in symbols:
                row_data = {"symbol": symbol}
                for name in names:
                    matching_keys = [k for k in self._online_db.keys() if k[0] == name and k[2] == symbol]
                    if not matching_keys:
                        continue
                    latest_key = sorted(matching_keys, key=lambda k: _parse_semver(k[1]))[-1]
                    latest_df = self._online_db[latest_key]
                    if len(latest_df) > 0:
                        row_data[name] = latest_df.iloc[0][name]
                        row_data[f"{name}_as_of"] = latest_df.iloc[0]["as_of"]
                rows.append(row_data)
        return pd.DataFrame(rows)
