"""Rebalancer validating threshold drift limits and generating trade plans.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from research_platform.portfolio_engine.interfaces import IRebalancer
from research_platform.portfolio_engine.models import PortfolioWeights, RebalancePlan


class PortfolioRebalancer(IRebalancer):
    """Monitors drift deviations and schedules calendar/volatility adjustments."""

    def __init__(self, drift_threshold: float = 0.05) -> None:
        self.drift_threshold = drift_threshold

    def evaluate_rebalance(
        self,
        current: PortfolioWeights,
        target: PortfolioWeights
    ) -> Optional[RebalancePlan]:
        """Evaluate if drift triggers require rebalance executions."""
        trades_needed = {}
        trigger = False
        
        # Combine all symbols from current and target
        all_symbols = set(current.weights.keys()).union(target.weights.keys())

        for sym in all_symbols:
            w_curr = current.weights.get(sym, 0.0)
            w_targ = target.weights.get(sym, 0.0)

            drift = abs(w_curr - w_targ)
            if drift > self.drift_threshold:
                trigger = True

            diff = w_targ - w_curr
            if diff != 0.0:
                trades_needed[sym] = diff

        if trigger:
            return RebalancePlan(
                plan_id=str(uuid.uuid4()),
                target_weights=target,
                current_weights=current,
                trades_needed=trades_needed,
                trigger_type="DRIFT",
                timestamp=datetime.now(timezone.utc)
            )

        return None
