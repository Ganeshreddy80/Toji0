"""Setup Validator for Strategy Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from confluence.core.models import ConfluenceState


class SetupValidator:
    """Validator to ensure baseline conditions are met before running strategy logic."""

    @staticmethod
    def is_valid_context(
        market_state: MarketState,
        confluence_state: ConfluenceState | None,
    ) -> bool:
        """Validate if baseline state permits trade generation."""
        if market_state is None:
            return False

        # If confluence is too low (e.g. below 50.0), or has critical conflicts, block it
        if confluence_state is not None:
            if confluence_state.score.overall_score < 50.0:
                return False
            # Block if conflict penalty is extremely high (e.g. >= 5.0 out of 6.0 max)
            if confluence_state.score.conflict_penalty >= 5.0:
                return False

        return True
