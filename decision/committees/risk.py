"""Risk Committee implementation for monitoring portfolio and capital preservation metrics."""

from __future__ import annotations

from typing import Any
import pandas as pd
from decision.committees.base import BaseCommittee
from decision.models import CommitteeVote, DecisionState
from analytics.risk_metrics.calculator import RiskMetricsCalculator


class RiskCommittee(BaseCommittee):
    """Monitors capital drawdown, VaR/CVaR thresholds, exposure limits, and probability of ruin."""

    def __init__(
        self,
        default_max_drawdown: float = 0.15,
        default_max_var: float = 0.04,
        default_max_ruin_prob: float = 0.05,
    ) -> None:
        """Initialize the RiskCommittee.

        Args:
            default_max_drawdown: Maximum permitted peak-to-trough drawdown threshold.
            default_max_var: Maximum permitted daily Value at Risk threshold.
            default_max_ruin_prob: Maximum permitted probability of ruin.
        """
        self.default_max_drawdown = default_max_drawdown
        self.default_max_var = default_max_var
        self.default_max_ruin_prob = default_max_ruin_prob

    def vote(self, context: dict[str, Any]) -> CommitteeVote:
        """Evaluate VaR, CVaR, drawdown, and exposure limits to submit a vote.

        Args:
            context: Context containing 'returns', 'equity_series', 'positions_value',
                     'total_equity', 'win_rate', 'payoff_ratio', 'fraction_risked',
                     and optional thresholds.

        Returns:
            CommitteeVote.
        """
        # Load thresholds
        max_dd = context.get("max_drawdown_limit", self.default_max_drawdown)
        max_var = context.get("max_var_limit", self.default_max_var)
        max_ruin = context.get("max_ruin_prob_limit", self.default_max_ruin_prob)

        # 1. Gather returns & equity metrics
        returns_data = context.get("returns", [])
        equity_data = context.get("equity_series", [])

        current_dd = 0.0
        if len(equity_data) > 0:
            current_dd = abs(RiskMetricsCalculator.maximum_drawdown(equity_data))

        current_var = 0.0
        current_cvar = 0.0
        if len(returns_data) > 1:
            current_var = RiskMetricsCalculator.value_at_risk(returns_data, confidence_level=0.95)
            current_cvar = RiskMetricsCalculator.conditional_value_at_risk(returns_data, confidence_level=0.95)

        # 2. Exposure checks
        pos_values = context.get("positions_value", {})
        tot_equity = context.get("total_equity", 100000.0)
        net_exp, gross_exp = RiskMetricsCalculator.portfolio_exposure(pos_values, tot_equity)

        # 3. Probability of Ruin
        win_rate = context.get("win_rate", 0.5)
        payoff = context.get("payoff_ratio", 2.0)
        risk_frac = context.get("fraction_risked", 0.02)
        ruin_prob = RiskMetricsCalculator.risk_of_ruin(win_rate, payoff, risk_frac)

        metrics = {
            "current_drawdown": current_dd,
            "value_at_risk": current_var,
            "conditional_var": current_cvar,
            "net_exposure": net_exp,
            "gross_exposure": gross_exp,
            "ruin_probability": ruin_prob,
        }

        # --- Evaluative Rules ---
        # Severe Drawdown or VaR breach -> Emergency Exit
        if current_dd > max_dd or current_var > max_var:
            return CommitteeVote(
                committee_name="Risk",
                vote_state=DecisionState.EMERGENCY_EXIT,
                score=-1.0,
                confidence=0.95,
                metrics=metrics,
                reason=f"Drawdown ({current_dd:.2%}) or VaR ({current_var:.2%}) exceeds risk limits",
            )

        # High probability of ruin -> Exit
        if ruin_prob > max_ruin:
            return CommitteeVote(
                committee_name="Risk",
                vote_state=DecisionState.EXIT,
                score=-0.6,
                confidence=0.90,
                metrics=metrics,
                reason=f"Probability of ruin ({ruin_prob:.2%}) exceeds safety limits ({max_ruin:.2%})",
            )

        # High Gross Exposure or near max drawdown -> Reduce
        if gross_exp > 1.5 or current_dd > (max_dd * 0.8):
            return CommitteeVote(
                committee_name="Risk",
                vote_state=DecisionState.REDUCE,
                score=0.20,
                confidence=0.85,
                metrics=metrics,
                reason="Approaching portfolio exposure limits or drawdown warning threshold",
            )

        # Moderate Gross Exposure -> Hold
        if gross_exp > 1.2:
            return CommitteeVote(
                committee_name="Risk",
                vote_state=DecisionState.HOLD,
                score=0.60,
                confidence=0.80,
                metrics=metrics,
                reason="Leverage/exposure is moderate. Restricting further additions",
            )

        # Clean Risk Profile -> Enter
        return CommitteeVote(
            committee_name="Risk",
            vote_state=DecisionState.ENTER,
            score=0.90,
            confidence=0.90,
            metrics=metrics,
            reason="All risk metrics (VaR, Drawdown, Ruin Probability) are within safe boundaries",
        )
