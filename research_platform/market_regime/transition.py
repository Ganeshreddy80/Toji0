"""Regime transitions tracker and probability calculator.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from research_platform.market_regime.models import MarketRegime, RegimeTransition

logger = logging.getLogger(__name__)


class RegimeTransitionEngine:
    """Detects regime change points and dynamically computes transition probability matrices."""

    def __init__(self) -> None:
        # Tracks transition counts: key is (old_state_str, new_state_str) -> count
        # State representation: f"{regime_type}_{volatility}_{liquidity}"
        self._transition_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    def _get_state_str(self, regime: Optional[MarketRegime]) -> str:
        if not regime:
            return "NONE"
        return f"{regime.regime_type.value}_{regime.volatility.value}_{regime.liquidity.value}"

    def check_transition(self, old_regime: Optional[MarketRegime], new_regime: MarketRegime) -> Optional[RegimeTransition]:
        """Verify if a transition has occurred. If so, return a calculated RegimeTransition."""
        if not old_regime:
            # First record, no transition
            return None

        old_state = self._get_state_str(old_regime)
        new_state = self._get_state_str(new_regime)

        if old_state == new_state:
            return None

        # Record transition count
        self._transition_counts[(old_state, new_state)] += 1

        # Calculate probability based on past transitions out of old_state
        total_transitions_from_old = sum(count for (src, dst), count in self._transition_counts.items() if src == old_state)
        probability = 1.0
        if total_transitions_from_old > 0:
            probability = self._transition_counts[(old_state, new_state)] / total_transitions_from_old

        transition = RegimeTransition(
            symbol=new_regime.symbol,
            old_regime=old_regime,
            new_regime=new_regime,
            probability=probability
        )
        logger.info("Regime transition detected for %s: %s -> %s (Prob: %.2f)",
                    new_regime.symbol, old_state, new_state, probability)
        return transition
