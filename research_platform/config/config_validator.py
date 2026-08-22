"""R51 Configuration validator check routines.
"""

from __future__ import annotations

from typing import Dict, Any, List
from pydantic import ValidationError
from research_platform.config.models import CentralConfig


class ConfigValidator:
    """Validates structural configuration structures and bounds checks."""

    @staticmethod
    def validate(config_dict: Dict[str, Any]) -> List[str]:
        """Runs validation checks. Returns a list of error strings if any fail."""
        errors: List[str] = []
        try:
            # 1. Structural pydantic validation
            CentralConfig.model_validate(config_dict)
        except ValidationError as e:
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err["loc"])
                errors.append(f"Field '{loc}': {err['msg']}")

        # 2. Custom boundary checks
        db = config_dict.get("database", {})
        if isinstance(db, dict):
            port = db.get("port", 5432)
            if not (0 < port < 65536):
                errors.append(f"Database port must be within bounds (0, 65536), found: {port}")

        risk = config_dict.get("risk", {})
        if isinstance(risk, dict):
            slippage = risk.get("max_slippage_pct", 0.0)
            if slippage < 0.0 or slippage > 0.5:
                errors.append(f"Risk max_slippage_pct must be between 0.0 and 0.5, found: {slippage}")

        return errors
