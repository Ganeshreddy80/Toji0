"""Opportunity Engine for ranking and evaluating trading opportunities."""

from __future__ import annotations

import math
from intelligence.models import Opportunity, RiskGrade


class OpportunityEngine:
    """Evaluates and ranks market opportunities based on statistical evidence, risk, and timing."""

    def __init__(
        self,
        weight_analytics: float = 0.35,
        weight_timing: float = 0.25,
        weight_risk: float = 0.25,
        weight_knowledge: float = 0.15,
    ) -> None:
        """Initialize the OpportunityEngine.

        Args:
            weight_analytics: Sizing factor for strategy backtest stats.
            weight_timing: Sizing factor for execution window and signal age.
            weight_risk: Sizing factor for asset health and risk grade.
            weight_knowledge: Sizing factor for supporting rules and beliefs count.
        """
        # Ensure weights sum to 1.0 (normalize them)
        total = weight_analytics + weight_timing + weight_risk + weight_knowledge
        self.w_analytics = weight_analytics / total
        self.w_timing = weight_timing / total
        self.w_risk = weight_risk / total
        self.w_knowledge = weight_knowledge / total

    def evaluate_opportunity(
        self,
        symbol: str,
        strategy_id: str,
        regime: str,
        timing_window: str,
        win_rate: float,
        sharpe: float,
        timing_decay: float,
        risk_grade: RiskGrade,
        evidence_count: int,
    ) -> Opportunity:
        """Score a single opportunity and compile its Pydantic model.

        Args:
            symbol: Target symbol.
            strategy_id: Strategy identifier.
            regime: Current market regime.
            timing_window: Recommended execution window.
            win_rate: Backtested strategy win rate (0.0 to 1.0).
            sharpe: Backtested strategy Sharpe ratio.
            timing_decay: Freshness coefficient (0.0 to 1.0).
            risk_grade: Evaluated RiskGrade.
            evidence_count: Count of supporting rules/beliefs in knowledge base.

        Returns:
            Opportunity object.
        """
        # 1. Analytics Score (0.0 to 1.0)
        # Saturated Sharpe scaling (3.0 Sharpe = 1.0 max)
        sharpe_score = min(1.0, max(0.0, sharpe / 3.0))
        analytics_score = 0.6 * win_rate + 0.4 * sharpe_score

        # 2. Timing Score (0.0 to 1.0)
        # Direct relationship to signal freshness
        timing_score = max(0.0, min(1.0, timing_decay))

        # 3. Risk Score (0.0 to 1.0)
        risk_map = {
            RiskGrade.A: 1.0,
            RiskGrade.B: 0.8,
            RiskGrade.C: 0.6,
            RiskGrade.D: 0.3,
            RiskGrade.F: 0.0,
        }
        risk_score = risk_map[risk_grade]

        # 4. Knowledge Score (0.0 to 1.0)
        # Diminishing returns scaling on evidence counts (e.g. 5+ pieces is near 1.0)
        knowledge_score = 1.0 - math.exp(-evidence_count / 2.5)

        # 5. Weighted Combination
        final_score = (
            self.w_analytics * analytics_score
            + self.w_timing * timing_score
            + self.w_risk * risk_score
            + self.w_knowledge * knowledge_score
        )

        return Opportunity(
            symbol=symbol,
            strategy_id=strategy_id,
            score=min(1.0, max(0.0, final_score)),
            regime=regime,
            timing_window=timing_window,
            risk_grade=risk_grade,
            evidence_count=evidence_count,
        )

    def rank_opportunities(self, opportunities: list[Opportunity]) -> list[Opportunity]:
        """Rank opportunities in descending order of score.

        Args:
            opportunities: List of Opportunity objects.

        Returns:
            Sorted list of Opportunity objects.
        """
        return sorted(opportunities, key=lambda x: x.score, reverse=True)
