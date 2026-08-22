"""Intelligent Memory Cache for feature calculations.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Dict, Optional
import pandas as pd

from research_platform.feature_platform.interfaces import IFeatureCache


class FeatureCache(IFeatureCache):
    """Thread-safe, versioned in-memory cache for computed dataframes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: Dict[str, pd.DataFrame] = {}

    @staticmethod
    def generate_key(name: str, version: str, symbol: str, params: dict) -> str:
        """Create a hash-based key for cache lookups."""
        param_str = str(sorted(params.items()))
        raw_key = f"{name}:{version}:{symbol}:{param_str}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Retrieve a cached calculation."""
        with self._lock:
            df = self._cache.get(cache_key)
            return df.copy() if df is not None else None

    def set(self, cache_key: str, df: pd.DataFrame) -> None:
        """Commit a calculation to cache."""
        with self._lock:
            self._cache[cache_key] = df.copy()

    def invalidate(self, cache_key: str) -> None:
        """Invalidate specific cache entries."""
        with self._lock:
            self._cache.pop(cache_key, None)

    def clear(self) -> None:
        """Clear all cache values."""
        with self._lock:
            self._cache.clear()
