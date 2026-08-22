"""Storage layer loading and saving dataframes with compression.
"""

from __future__ import annotations

import os
import pandas as pd
from typing import Optional


class StorageLayer:
    """Manages CSV and Parquet read/write operations with compression."""

    @staticmethod
    def save_dataframe(
        df: pd.DataFrame,
        path: str,
        format_type: str = "CSV",
        compression: Optional[str] = None
    ) -> int:
        """Write DataFrame to disk. Returns size in bytes."""
        # Ensure directories exist
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if format_type.upper() == "CSV":
            df.to_csv(path, index=False, compression=compression)
        elif format_type.upper() == "PARQUET":
            df.to_parquet(path, index=False, compression=compression)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

        return os.path.getsize(path)

    @staticmethod
    def load_dataframe(
        path: str,
        format_type: str = "CSV",
        lazy: bool = False
    ) -> pd.DataFrame:
        """Read DataFrame from disk. If lazy is True, return standard DataFrame proxy."""
        if format_type.upper() == "CSV":
            return pd.read_csv(path)
        elif format_type.upper() == "PARQUET":
            return pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")
class LazyDataFrameProxy:
    """Simulates lazy reading or memory mapping for data access."""

    def __init__(self, path: str, format_type: str) -> None:
        self.path = path
        self.format_type = format_type
        self._df: Optional[pd.DataFrame] = None

    def load(self) -> pd.DataFrame:
        if self._df is None:
            self._df = StorageLayer.load_dataframe(self.path, self.format_type)
        return self._df
