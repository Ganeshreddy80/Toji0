"""Dataset versioning and content SHA256 fingerprinting.
"""

from __future__ import annotations

import hashlib
import pandas as pd
from typing import Dict, List

from research_platform.data_platform.models import DatasetFingerprint


class DatasetVersioning:
    """Computes SHA256 content checksums and validates schemas changes."""

    @staticmethod
    def generate_fingerprint(df: pd.DataFrame) -> DatasetFingerprint:
        """Generate a deterministic SHA256 checksum representing DataFrame content."""
        # Convert DataFrame to a deterministic CSV string representation for hashing
        csv_str = df.to_csv(index=False).encode("utf-8")
        h = hashlib.sha256(csv_str).hexdigest()
        return DatasetFingerprint(hash_sha256=h)

    @staticmethod
    def validate_schema(df: pd.DataFrame, expected_types: Dict[str, str]) -> bool:
        """Verify DataFrame schema matches expected column names and types.

        Args:
            df: DataFrame to validate.
            expected_types: Dict mapping column name to pandas dtype string.
        """
        for col, expected_type in expected_types.items():
            if col not in df.columns:
                return False
            # Basic type check: e.g. check if subclass or type name is compatible
            actual_type = str(df[col].dtype)
            if "int" in expected_type and "int" not in actual_type:
                return False
            if "float" in expected_type and "float" not in actual_type:
                return False
        return True
