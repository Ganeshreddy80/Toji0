"""Explanation Engine explaining trade events or drawdowns.
"""

from __future__ import annotations

import uuid

from research_platform.ai_intelligence.models import Explanation


class ExplanationEngine:
    """Provides natural-language explanations referencing metric boundaries."""

    def explain_metric_event(self, metric: str, value: float, rationale: str) -> Explanation:
        """Construct Explanation object."""
        return Explanation(
            explanation_id=str(uuid.uuid4()),
            metric_referenced=metric,
            narrative=f"Metric {metric} reached value {value:.2f}. Rationale: {rationale}"
        )
