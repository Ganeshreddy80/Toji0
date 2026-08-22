"""Confidence scoring calculator based on evidence count, quality, recency, and conflicts."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from knowledge.models import Evidence


class ConfidenceCalculator:
    """Computes evidence-backed confidence scores for platform knowledge."""

    @staticmethod
    def calculate_confidence(
        evidence_list: list[Evidence],
        has_conflict: bool = False,
        decay_half_life_days: float = 365.0,
    ) -> float:
        """Compute a confidence score between 0.0 and 1.0 for a rule or belief.
        
        Formula elements:
        1. Evidence Volume: Asymptotically approaches 1.0 with more evidence: 1 - exp(-0.4 * count)
        2. Evidence Quality: Scales based on sample size (sample_size / (sample_size + 30))
        3. Recency Decay: Exponential decay based on time elapsed since evidence creation.
        4. Inconsistency Discount: 50% penalty if a conflict exists.
        """
        n = len(evidence_list)
        if n == 0:
            return 0.0
            
        # 1. Volume Factor
        volume_factor = 1.0 - math.exp(-0.4 * n)
        
        # 2. Quality & Recency factors calculation
        quality_factors = []
        decay_factors = []
        
        now = datetime.now(timezone.utc)
        
        for e in evidence_list:
            # Quality factor based on sample size (e.g. number of trades or observations)
            sample_size = e.sample_size if e.sample_size > 0 else 30
            quality = sample_size / (sample_size + 30)
            quality_factors.append(quality)
            
            # Recency factor
            age_days = max(0.0, (now - e.created_at).total_seconds() / 86400.0)
            # lambda = ln(2) / half_life
            decay_lambda = math.log(2.0) / decay_half_life_days
            decay = math.exp(-decay_lambda * age_days)
            decay_factors.append(decay)
            
        mean_quality = sum(quality_factors) / len(quality_factors) if quality_factors else 1.0
        mean_decay = sum(decay_factors) / len(decay_factors) if decay_factors else 1.0
        
        # Base confidence combining factors
        confidence = volume_factor * mean_quality * mean_decay
        
        # 3. Conflict penalty
        if has_conflict:
            confidence *= 0.5
            
        return float(max(0.0, min(1.0, confidence)))
