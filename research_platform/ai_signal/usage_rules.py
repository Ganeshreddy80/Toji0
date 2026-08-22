"""Rules and policy enforcement for OpenRouter / LLM integrations.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AIUsageController:
    """Enforces boundaries on LLM actions to prevent autonomous trading without gatekeepers."""

    ALLOWED_CAPABILITIES = [
        "explain_trade",
        "summarize_market",
        "analyze_performance",
        "generate_report"
    ]

    FORBIDDEN_KEYWORDS = [
        "submit_order",
        "submit_intent",
        "change_risk",
        "disable_safety",
        "enable_live_mode",
        "bypass_safety",
        "execute_trade"
    ]

    @classmethod
    def validate_action(cls, action: str) -> bool:
        """Evaluate action. Raises PermissionError if a forbidden capability is requested."""
        action_lower = action.lower()
        for kw in cls.FORBIDDEN_KEYWORDS:
            if kw in action_lower:
                err_msg = f"LLM Policy Violation: Capability '{action}' contains forbidden operation '{kw}'."
                logger.error(err_msg)
                raise PermissionError(err_msg)
        return True
