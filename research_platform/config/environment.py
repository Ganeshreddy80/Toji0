"""R51 Environment configuration overrides.
"""

from __future__ import annotations

import os
from typing import Dict, Any


class EnvironmentLoader:
    """Loads system environment variables with target prefix 'TOJI_'."""

    @staticmethod
    def load_from_env() -> Dict[str, Any]:
        """Scans environment and maps TOJI_ variables into nested overrides dictionary."""
        overrides: Dict[str, Any] = {}
        for key, value in os.environ.items():
            if key.startswith("TOJI_"):
                # E.g. TOJI_DATABASE_HOST -> database: { host: value }
                parts = key[5:].lower().split("_")
                if len(parts) == 2:
                    section, field = parts[0], parts[1]
                    if section not in overrides:
                        overrides[section] = {}
                    # Simple type parsing
                    if value.isdigit():
                        overrides[section][field] = int(value)
                    elif value.replace(".", "", 1).isdigit():
                        overrides[section][field] = float(value)
                    elif value.upper() in ("TRUE", "FALSE"):
                        overrides[section][field] = value.upper() == "TRUE"
                    else:
                        overrides[section][field] = value
        return overrides
