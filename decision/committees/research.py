"""Research Committee implementation for assessing strategy metrics and significance."""

from __future__ import annotations

from typing import Any
from decision.committees.base import BaseCommittee
from decision.models import CommitteeVote, DecisionState


class ResearchCommittee(BaseCommittee):
    """Evaluates strategy validation significance, backtest metrics, and research quality to submit votes."""

    def vote(self, context: dict[str, Any]) -> CommitteeVote:
        """Submit a vote based on research metrics: win_rate, sharpe, p_value, t_stat, validation.

        Args:
            context: Context containing 'win_rate', 'sharpe', 'p_value', 't_stat',
                     and optional 'sortino' or 'backtest_robustness'.

        Returns:
            CommitteeVote.
        """
        win_rate = context.get("win_rate", 0.5)
        sharpe = context.get("sharpe", 1.0)
        p_value = context.get("p_value", 0.05)
        t_stat = context.get("t_stat", 2.0)
        validation_passed = context.get("experiment_validation", "passed").lower() == "passed"
        robustness = context.get("backtest_robustness_score", 1.0)

        # Base evaluations
        is_significant = p_value < 0.05 or t_stat >= 2.0
        is_highly_significant = p_value < 0.01 or t_stat >= 3.0

        metrics = {
            "win_rate": win_rate,
            "sharpe": sharpe,
            "p_value": p_value,
            "t_stat": t_stat,
            "validation_passed": validation_passed,
            "robustness": robustness,
        }

        # Exit conditions
        if sharpe < 0.0 or not validation_passed:
            return CommitteeVote(
                committee_name="Research",
                vote_state=DecisionState.EXIT,
                score=-0.5,
                confidence=0.8,
                metrics=metrics,
                reason="Negative strategy Sharpe or strategy validation failed",
            )

        # Enter conditions
        if sharpe >= 2.0 and win_rate >= 0.55 and is_highly_significant and robustness >= 0.8:
            return CommitteeVote(
                committee_name="Research",
                vote_state=DecisionState.ENTER,
                score=0.95,
                confidence=0.9,
                metrics=metrics,
                reason="Highly significant backtest results with premium Sharpe ratio and strong validation robustness",
            )
        elif sharpe >= 1.2 and win_rate >= 0.50 and is_significant:
            return CommitteeVote(
                committee_name="Research",
                vote_state=DecisionState.READY,
                score=0.75,
                confidence=0.8,
                metrics=metrics,
                reason="Significant backtest parameters with acceptable Sharpe ratio and win rate",
            )
        elif sharpe >= 0.8 and win_rate >= 0.48:
            return CommitteeVote(
                committee_name="Research",
                vote_state=DecisionState.WATCH,
                score=0.40,
                confidence=0.6,
                metrics=metrics,
                reason="Marginal Sharpe ratio. Placed on watchlist for tracking",
            )
        else:
            return CommitteeVote(
                committee_name="Research",
                vote_state=DecisionState.IGNORE,
                score=0.0,
                confidence=0.5,
                metrics=metrics,
                reason="Poor strategy parameters or statistical significance below limits",
            )
