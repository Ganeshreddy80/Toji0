"""Validator verifying configuration parameter shapes and formats.
"""

from __future__ import annotations

from typing import Dict, Any
from research_platform.configuration.interfaces import IValidator


class Validator(IValidator):
    """Checks schema layouts and key value formats."""

    def validate(self, scope: str, params: Dict[str, Any]) -> None:
        if not isinstance(params, dict):
            raise ValueError("Invalid Configuration Parameters: Parameters must be a dictionary.")
        
        # Enforce basic type checking for global or risk parameters
        if scope == "RISK":
            limit = params.get("drawdown_limit")
            if limit is not None and not isinstance(limit, (int, float)):
                raise ValueError("Invalid Risk Configuration: 'drawdown_limit' must be a numeric value.")
