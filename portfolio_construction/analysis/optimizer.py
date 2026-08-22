"""Portfolio optimization engine implementing IPortfolioOptimizer."""

from __future__ import annotations

import logging
from typing import Dict, List

from portfolio_construction.core.enums import OptimizationObjective
from portfolio_construction.core.interfaces import IPortfolioOptimizer
from portfolio_construction.core.models import PortfolioCandidate, PortfolioConstraintConfig

logger = logging.getLogger(__name__)


class PortfolioOptimizer(IPortfolioOptimizer):
    """Calculates optimal target weights across candidate assets under constraints."""

    def optimize(
        self,
        candidates: List[PortfolioCandidate],
        correlation_matrix: Dict[str, Dict[str, float]],
        config: PortfolioConstraintConfig,
        objective: OptimizationObjective = OptimizationObjective.CONFIDENCE_WEIGHTED,
    ) -> Dict[str, float]:
        """
        Calculate normalized target weights [0.0, 1.0] for candidate assets.
        Isolates solver failures so an optimization crash falls back to safe weighting.
        """
        if not candidates:
            return {}

        try:
            if objective == OptimizationObjective.EQUAL_WEIGHT:
                raw_weights = self._equal_weight(candidates)
            elif objective == OptimizationObjective.CONFIDENCE_WEIGHTED:
                raw_weights = self._confidence_weighted(candidates)
            elif objective == OptimizationObjective.RISK_PARITY:
                raw_weights = self._risk_parity(candidates)
            elif objective == OptimizationObjective.MEAN_VARIANCE:
                raw_weights = self._mean_variance(candidates, correlation_matrix)
            else:
                raw_weights = self._confidence_weighted(candidates)

            # Cap individual weights and re-normalize
            return self._apply_weight_caps(raw_weights, config)

        except Exception as e:
            logger.error("PortfolioOptimizer: Solver failure for objective %s: %s. Falling back to confidence weighting.", objective, e, exc_info=True)
            try:
                raw_weights = self._confidence_weighted(candidates)
                return self._apply_weight_caps(raw_weights, config)
            except Exception as fb_err:
                logger.error("PortfolioOptimizer: Fallback optimizer failed: %s. Returning empty allocation.", fb_err)
                return {}

    def _equal_weight(self, candidates: List[PortfolioCandidate]) -> Dict[str, float]:
        n = len(candidates)
        if n == 0:
            return {}
        w = 1.0 / n
        return {c.symbol: round(w, 4) for c in candidates}

    def _confidence_weighted(self, candidates: List[PortfolioCandidate]) -> Dict[str, float]:
        total_conf = sum(c.confidence for c in candidates)
        if total_conf <= 0.0:
            return self._equal_weight(candidates)
        return {c.symbol: round(c.confidence / total_conf, 4) for c in candidates}

    def _risk_parity(self, candidates: List[PortfolioCandidate]) -> Dict[str, float]:
        # Inverse volatility weighting as risk parity proxy
        inv_vols = []
        for c in candidates:
            vol = c.volatility if c.volatility > 0.0001 else 0.20
            inv_vols.append(1.0 / vol)
        sum_inv = sum(inv_vols)
        if sum_inv <= 0.0:
            return self._equal_weight(candidates)
        return {c.symbol: round(inv / sum_inv, 4) for c, inv in zip(candidates, inv_vols)}

    def _mean_variance(
        self, candidates: List[PortfolioCandidate], correlation_matrix: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        # Mean-variance proxy weighting expected return divided by volatility
        scores = []
        for c in candidates:
            ret = c.expected_return if c.expected_return > 0.0 else c.confidence
            vol = c.volatility if c.volatility > 0.0001 else 0.20
            scores.append(ret / vol)
        sum_score = sum(scores)
        if sum_score <= 0.0:
            return self._equal_weight(candidates)
        return {c.symbol: round(s / sum_score, 4) for c, s in zip(candidates, scores)}

    def _apply_weight_caps(
        self, raw_weights: Dict[str, float], config: PortfolioConstraintConfig
    ) -> Dict[str, float]:
        """Iteratively apply max_weight_per_asset and min_weight_per_asset caps and renormalize."""
        if not raw_weights:
            return {}

        weights = dict(raw_weights)
        cap = config.max_weight_per_asset
        floor = config.min_weight_per_asset

        # Step 1: Filter out any below floor
        weights = {s: w for s, w in weights.items() if w >= floor - 0.0001}

        if not weights:
            return {}

        # Step 2: Cap at max_weight_per_asset
        for s in weights:
            if weights[s] > cap:
                weights[s] = cap

        # Step 3: Re-normalize if sum > 1.0
        total = sum(weights.values())
        if total > 1.0:
            weights = {s: round(w / total, 4) for s, w in weights.items()}

        # Final pass: Ensure no single asset exceeds cap after rounding
        for s in weights:
            if weights[s] > cap:
                weights[s] = cap

        return weights
