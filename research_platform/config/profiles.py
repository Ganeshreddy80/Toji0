"""R51 Profile maps.
"""

from __future__ import annotations

from typing import Dict, Any
from research_platform.config.defaults import (
    DEFAULT_DEV_PROFILE,
    DEFAULT_PAPER_PROFILE,
    DEFAULT_PROD_PROFILE
)


class ConfigProfileLoader:
    """Helper class coordinating profile mapping and loading."""

    @staticmethod
    def get_profile_defaults(profile_name: str) -> Dict[str, Any]:
        """Fetch matching default profile configurations."""
        name_clean = profile_name.strip().upper()
        if name_clean == "PROD":
            return DEFAULT_PROD_PROFILE
        elif name_clean == "DEV":
            return DEFAULT_DEV_PROFILE
        else:
            return DEFAULT_PAPER_PROFILE
