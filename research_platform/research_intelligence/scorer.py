"""Research grading and quality scorecard engine implementing IResearchScorer.
"""

from __future__ import annotations

import logging
from research_platform.research_intelligence.interfaces import IResearchScorer
from research_platform.research_intelligence.models import ResearchScore

logger = logging.getLogger(__name__)


class ResearchScorer(IResearchScorer):
    """Calculates multidimensional quality scores out of 10 for research experiments."""

    def score_research(
        self,
        hypothesis_id: str,
        sharpe: float,
        drawdown: float,
        win_rate: float,
        stability: float
    ) -> ResearchScore:
        """Calculate quality scorecard profile."""
        # Sharpe contribution (capped at 3.0, scaled to max 6.0 points)
        sharpe_points = min(max(sharpe, 0.0), 3.0) * 2.0

        # Drawdown contribution (capped at 20% drawdown, scaled to max 2.0 points)
        # 0% DD -> 2.0 points, 20% DD -> 0 points
        drawdown_points = max(0.0, 2.0 - (drawdown * 10.0))

        # Win Rate contribution (scaled to max 1.0 point)
        win_rate_points = min(max(win_rate, 0.0), 1.0) * 1.0

        # Parameter stability index contribution (scaled to max 1.0 point)
        stability_points = min(max(stability, 0.0), 1.0) * 1.0

        quality_score = sharpe_points + drawdown_points + win_rate_points + stability_points
        # Clamp between 0.0 and 10.0
        quality_score = min(max(quality_score, 0.0), 10.0)

        logger.info("Scored hypothesis '%s': %.2f/10.0 (Sharpe: %.2f, DD: %.2f%%)",
                    hypothesis_id, quality_score, sharpe, drawdown * 100.0)

        return ResearchScore(
            hypothesis_id=hypothesis_id,
            sharpe=sharpe,
            drawdown=drawdown,
            win_rate=win_rate,
            parameter_stability=stability,
            quality_score=quality_score
        )
