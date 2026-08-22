"""Pattern Quality Engine coordinator for price action patterns."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternCandidate, PatternMatch, PatternQuality
from price_action.quality.geometry_score import evaluate_geometry
from price_action.quality.symmetry_score import evaluate_symmetry
from price_action.quality.breakout_score import evaluate_breakout
from price_action.quality.touch_score import evaluate_touches
from price_action.quality.regression_score import evaluate_regression
from price_action.quality.volume_score import evaluate_volume
from price_action.quality.volatility_score import evaluate_volatility
from price_action.quality.age_score import evaluate_age
from price_action.quality.completion_score import evaluate_completion
from price_action.quality.confidence import evaluate_confidence

logger = logging.getLogger(__name__)


class PatternQualityEngine:
    """Evaluates the quality of every detected chart pattern using deterministic metrics."""

    def evaluate_candidate(self, candidate: PatternCandidate, market_state: MarketState | None = None) -> PatternQuality:
        """Evaluate a PatternCandidate."""
        return self._evaluate(candidate, market_state)

    def evaluate_match(self, match: PatternMatch, market_state: MarketState | None = None) -> PatternQuality:
        """Evaluate a PatternMatch."""
        return self._evaluate(match, market_state)

    def _evaluate(self, pattern: PatternCandidate | PatternMatch, market_state: MarketState | None = None) -> PatternQuality:
        # Run sub-scorers
        geometry = evaluate_geometry(pattern)
        symmetry = evaluate_symmetry(pattern)
        breakout = evaluate_breakout(pattern)
        touches = evaluate_touches(pattern)
        regression = evaluate_regression(pattern)
        volume = evaluate_volume(pattern)
        volatility = evaluate_volatility(pattern)
        age = evaluate_age(pattern)
        completion = evaluate_completion(pattern)
        confidence = evaluate_confidence(pattern, market_state)

        # Weighted deterministic scoring
        # Weights:
        # Geometry: 20, Regression: 15, Touches: 15, Volume: 10, Volatility: 10,
        # Breakout: 10, Symmetry: 10, Age: 5, Completion: 5, Confidence: 10
        weights = {
            "geometry": 20.0,
            "regression": 15.0,
            "touches": 15.0,
            "volume": 10.0,
            "volatility": 10.0,
            "breakout": 10.0,
            "symmetry": 10.0,
            "age": 5.0,
            "completion": 5.0,
            "confidence": 10.0,
        }

        scores = {
            "geometry": geometry,
            "regression": regression,
            "touches": touches,
            "volume": volume,
            "volatility": volatility,
            "breakout": breakout,
            "symmetry": symmetry,
            "age": age,
            "completion": completion,
            "confidence": confidence,
        }

        weighted_sum = sum(scores[key] * weights[key] for key in weights)
        total_weight = sum(weights.values())
        overall_score = weighted_sum / total_weight if total_weight > 0.0 else 0.0

        ts = getattr(market_state, "updated_at", datetime.now(timezone.utc)) if market_state else datetime.now(timezone.utc)

        explanation = (
            f"Pattern '{pattern.pattern_type.value}' evaluated with overall quality score {overall_score:.2f}/100. "
            f"Key metrics: Geometry={geometry:.1f}, Regression={regression:.1f}, Symmetry={symmetry:.1f}, "
            f"Touches={touches:.1f}, Breakout={breakout:.1f}, Volume={volume:.1f}, Volatility={volatility:.1f}, "
            f"Age={age:.1f}, Completion={completion:.1f}, Confidence={confidence:.1f}."
        )

        return PatternQuality(
            overall_score=overall_score,
            geometry_score=geometry,
            symmetry_score=symmetry,
            breakout_score=breakout,
            regression_score=regression,
            touch_score=touches,
            volume_score=volume,
            volatility_score=volatility,
            age_score=age,
            completion_score=completion,
            confidence=confidence,
            evaluated_at=ts,
            explanation=explanation,
        )
