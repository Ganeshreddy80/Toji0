"""Portfolio Committee implementation for evaluating concentration and correlation limits."""

from __future__ import annotations

from typing import Any
from decision.committees.base import BaseCommittee
from decision.models import CommitteeVote, DecisionState


class PortfolioCommittee(BaseCommittee):
    """Evaluates asset concentration levels, cross-portfolio correlation thresholds, and diversification metrics."""

    def __init__(
        self,
        max_concentration_limit: float = 0.15,  # 15% maximum target size
        max_correlation_limit: float = 0.75,    # 0.75 maximum average correlation
    ) -> None:
        """Initialize the PortfolioCommittee.

        Args:
            max_concentration_limit: Maximum portfolio allocation cap for any single asset.
            max_correlation_limit: Maximum correlation tolerance with current holdings.
        """
        self.max_concentration_limit = max_concentration_limit
        self.max_correlation_limit = max_correlation_limit

    def vote(self, context: dict[str, Any]) -> CommitteeVote:
        """Assess portfolio constraints and submit a vote.

        Args:
            context: Context containing 'concentration_pct', 'average_correlation',
                     'suggested_allocation_pct', and optional limit overrides.

        Returns:
            CommitteeVote.
        """
        concentration = context.get("concentration_pct", 0.0)
        avg_corr = context.get("average_correlation", 0.0)
        suggested_alloc = context.get("suggested_allocation_pct", 0.05)

        max_conc = context.get("max_concentration_limit", self.max_concentration_limit)
        max_corr = context.get("max_correlation_limit", self.max_correlation_limit)

        metrics = {
            "concentration_pct": concentration,
            "average_correlation": avg_corr,
            "suggested_allocation_pct": suggested_alloc,
            "max_concentration_limit": max_conc,
            "max_correlation_limit": max_corr,
        }

        # Sizing / Concentration breaches
        if concentration >= max_conc:
            return CommitteeVote(
                committee_name="Portfolio",
                vote_state=DecisionState.REDUCE,
                score=0.10,
                confidence=0.90,
                metrics=metrics,
                reason=f"Current concentration ({concentration:.2%}) meets or exceeds maximum allocation limit ({max_conc:.2%})",
            )

        # Correlation breaches
        if avg_corr >= max_corr:
            return CommitteeVote(
                committee_name="Portfolio",
                vote_state=DecisionState.HOLD,
                score=0.40,
                confidence=0.85,
                metrics=metrics,
                reason=f"Asset correlation ({avg_corr:.2f}) meets or exceeds maximum correlation limit ({max_corr:.2f})",
            )

        # Insignificant allocation suggestion
        if suggested_alloc < 0.01:
            return CommitteeVote(
                committee_name="Portfolio",
                vote_state=DecisionState.IGNORE,
                score=0.0,
                confidence=0.70,
                metrics=metrics,
                reason="Suggested allocation percentage is negligible (< 1%)",
            )

        # Safe portfolio metrics
        return CommitteeVote(
            committee_name="Portfolio",
            vote_state=DecisionState.ENTER,
            score=0.85,
            confidence=0.80,
            metrics=metrics,
            reason="Asset offers favorable diversification properties with safe concentration and correlation profiles",
        )
