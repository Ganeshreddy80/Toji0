"""Recommendation Engine generating actionable optimization advisory alerts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.ai_intelligence.models import Recommendation


class RecommendationEngine:
    """Constructs advisory optimization suggestions."""

    def generate_recommendation(
        self,
        action: str,
        reasoning: str,
        confidence: float
    ) -> Recommendation:
        """Construct Recommendation object."""
        return Recommendation(
            recommendation_id=str(uuid.uuid4()),
            actionable_step=action,
            reasoning=reasoning,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )
