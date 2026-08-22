"""Portfolio constraint engine validating asset allocations against bounds."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from portfolio_construction.core.interfaces import IPortfolioConstraintEngine
from portfolio_construction.core.models import PortfolioCandidate, PortfolioConstraintConfig

logger = logging.getLogger(__name__)


class PortfolioConstraintEngine(IPortfolioConstraintEngine):
    """Validates candidate sets and proposed allocation weights against portfolio constraints."""

    def validate_constraints(
        self,
        candidates: List[PortfolioCandidate],
        weights: Dict[str, float],
        config: PortfolioConstraintConfig,
    ) -> Tuple[bool, List[str]]:
        """
        Validate portfolio target weights against all defined constraints.
        Returns tuple of (is_valid, list_of_violation_reasons).
        """
        violations: List[str] = []

        if not weights:
            return True, []

        # 1. Total Weight Cap (Sum <= 1.0)
        total_w = sum(weights.values())
        if total_w > 1.0001:
            violations.append(f"Total portfolio weight ({total_w:.4f}) exceeds 1.0 cap.")

        # 2. Max Positions Count
        active_count = len(weights)
        if active_count > config.max_positions:
            violations.append(f"Active positions count ({active_count}) exceeds max_positions ({config.max_positions}).")

        # 3. Individual Weight Bounds
        for sym, w in weights.items():
            if w > config.max_weight_per_asset + 0.0001:
                violations.append(f"Asset '{sym}' weight ({w:.4f}) exceeds max_weight_per_asset ({config.max_weight_per_asset:.4f}).")
            if w < config.min_weight_per_asset - 0.0001:
                violations.append(f"Asset '{sym}' weight ({w:.4f}) below min_weight_per_asset ({config.min_weight_per_asset:.4f}).")

        # 4. Sector Exposure Caps
        candidate_map = {c.symbol: c for c in candidates}
        sector_weights: Dict[str, float] = defaultdict(float)
        for sym, w in weights.items():
            candidate = candidate_map.get(sym)
            sec = candidate.sector if candidate else "GENERAL"
            sector_weights[sec] += w

        for sec, sec_w in sector_weights.items():
            if sec_w > config.max_sector_exposure + 0.0001:
                violations.append(f"Sector '{sec}' exposure ({sec_w:.4f}) exceeds max_sector_exposure ({config.max_sector_exposure:.4f}).")

        # 5. Min Portfolio Confidence Threshold
        if candidates:
            included_candidates = [candidate_map[sym] for sym in weights if sym in candidate_map]
            if included_candidates:
                avg_conf = sum(c.confidence for c in included_candidates) / len(included_candidates)
                if avg_conf < config.min_portfolio_confidence - 0.0001:
                    violations.append(f"Average portfolio confidence ({avg_conf:.4f}) below min_portfolio_confidence ({config.min_portfolio_confidence:.4f}).")

        is_valid = len(violations) == 0
        if not is_valid:
            logger.warning("PortfolioConstraintEngine: Constraint violations detected: %s", violations)

        return is_valid, violations
