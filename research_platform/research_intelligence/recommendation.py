"""Advisory recommendations and lessons generator implementing IRecommendationEngine.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional
from research_platform.research_intelligence.interfaces import IRecommendationEngine
from research_platform.research_intelligence.models import ExperimentRecommendation, ResearchHypothesis, ResearchScore

logger = logging.getLogger(__name__)


class RecommendationEngine(IRecommendationEngine):
    """Analyzes failures and successes to output parameter corrections and structural advice."""

    def generate_recommendations(self, hypothesis: ResearchHypothesis, score: ResearchScore) -> Optional[ExperimentRecommendation]:
        """Construct advisory parameter corrections recommendations."""
        changes = {}
        rationale = ""
        confidence = 0.5

        # Rule A: Drawdown exceeds threshold -> Tighter stop loss recommended
        if score.drawdown > 0.15:
            changes["stop_loss"] = 0.02
            changes["position_multiplier"] = 0.8
            rationale = "Drawdown exceeded 15% threshold. Recommend reducing leverage and tightening stop loss boundaries."
            confidence = 0.85

        # Rule B: Low Sharpe -> Check lookback parameter
        elif score.sharpe < 1.0:
            current_lookback = hypothesis.parameters.get("lookback", 20)
            changes["lookback"] = int(current_lookback * 1.5)
            rationale = "Sharpe ratio is under 1.0. Recommend expanding lookback window to filter false market noises."
            confidence = 0.70

        # Rule C: Highly successful -> Keep parameters, suggest promotion
        elif score.quality_score >= 7.0:
            changes = {}
            rationale = "Parameters verified as optimal. Suggest immediate progression to Backtesting or Walk-Forward phase."
            confidence = 0.90
            
        else:
            return None

        rec = ExperimentRecommendation(
            recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
            hypothesis_id=hypothesis.hypothesis_id,
            actionable_parameter_changes=changes,
            rationale=rationale,
            confidence=confidence
        )
        logger.info("Generated recommendation '%s' for hypothesis '%s': %s",
                    rec.recommendation_id, hypothesis.hypothesis_id, rationale)
        return rec
