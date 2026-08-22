"""Thread-safe Promotion Rules Engine for Advisory Model Evaluation (Sprint 11C)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.evaluation_metrics import MetricResult

logger = logging.getLogger(__name__)


class PromotionCriteria(BaseModel):
    """Immutable configurable threshold criteria for model promotion."""

    min_accuracy: float = Field(default=0.85, ge=0.0, le=1.0)
    max_val_loss: float = Field(default=0.25, ge=0.0)
    min_f1_score: float = Field(default=0.80, ge=0.0, le=1.0)
    min_sample_count: int = Field(default=100, ge=0)

    model_config = ConfigDict(frozen=True)


class PromotionRecommendation(BaseModel):
    """Immutable advisory-only promotion recommendation decision."""

    model_id: str = Field(..., description="Target model identifier.")
    is_eligible: bool = Field(..., description="True if model satisfies all criteria.")
    reasons: List[str] = Field(default_factory=list, description="Reasoning for pass/fail.")
    criteria_used: PromotionCriteria = Field(..., description="Criteria applied.")
    metrics_evaluated: MetricResult = Field(..., description="Metrics snapshot evaluated.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True, description="Advisory flag.")

    model_config = ConfigDict(frozen=True)


class PromotionRuleEngine:
    """Evaluates model promotion eligibility based on configurable metric thresholds.

    Returns purely advisory recommendations — does not perform autonomous deployment.
    """

    def __init__(self, default_criteria: Optional[PromotionCriteria] = None) -> None:
        self._default_criteria = default_criteria or PromotionCriteria()

    def evaluate_promotion(
        self,
        metrics: MetricResult,
        criteria: Optional[PromotionCriteria] = None,
    ) -> PromotionRecommendation:
        """Evaluate a MetricResult against thresholds and return advisory decision."""
        rule_set = criteria or self._default_criteria
        reasons: List[str] = []

        if metrics.accuracy < rule_set.min_accuracy:
            reasons.append(
                f"Accuracy {metrics.accuracy:.4f} is below minimum required {rule_set.min_accuracy:.4f}"
            )

        if metrics.val_loss > rule_set.max_val_loss:
            reasons.append(
                f"Validation loss {metrics.val_loss:.4f} exceeds maximum allowed {rule_set.max_val_loss:.4f}"
            )

        if metrics.f1_score < rule_set.min_f1_score:
            reasons.append(
                f"F1 score {metrics.f1_score:.4f} is below minimum required {rule_set.min_f1_score:.4f}"
            )

        if metrics.sample_count < rule_set.min_sample_count:
            reasons.append(
                f"Sample count {metrics.sample_count} is below minimum required {rule_set.min_sample_count}"
            )

        is_eligible = len(reasons) == 0
        if is_eligible:
            reasons.append("Model satisfies all promotion criteria thresholds")

        logger.info(
            "Promotion evaluation for model '%s': eligible=%s (%d check messages)",
            metrics.model_id, is_eligible, len(reasons)
        )

        return PromotionRecommendation(
            model_id=metrics.model_id,
            is_eligible=is_eligible,
            reasons=reasons,
            criteria_used=rule_set,
            metrics_evaluated=metrics,
        )
