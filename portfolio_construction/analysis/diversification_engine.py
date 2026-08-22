"""Diversification engine enforcing asset count and sector exposure caps."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from portfolio_construction.core.interfaces import IDiversificationEngine
from portfolio_construction.core.models import PortfolioCandidate, PortfolioConstraintConfig

logger = logging.getLogger(__name__)


class DiversificationEngine(IDiversificationEngine):
    """Enforces maximum position limits and sector exposure limits."""

    def apply_diversification(
        self,
        candidates: List[PortfolioCandidate],
        config: PortfolioConstraintConfig,
    ) -> Tuple[List[PortfolioCandidate], List[str]]:
        """
        Enforce max positions and sector exposure caps.
        Returns tuple of (diversified_candidates, rejected_symbols).
        """
        if not candidates:
            return [], []

        # Sort candidates by confidence descending
        sorted_candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)

        accepted: List[PortfolioCandidate] = []
        rejected_symbols: List[str] = []
        sector_counts: Dict[str, int] = defaultdict(int)

        # Estimate max allowed items per sector based on max_sector_exposure and min_weight_per_asset
        # E.g. if max_sector_exposure=0.50 and min_weight=0.05, max sector count can be computed or capped
        for candidate in sorted_candidates:
            # 1. Enforce max positions limit
            if len(accepted) >= config.max_positions:
                logger.info("DiversificationEngine: Reached max positions limit (%d)", config.max_positions)
                rejected_symbols.append(candidate.symbol)
                continue

            # 2. Enforce sector concentration limit
            sec = candidate.sector or "GENERAL"
            # Projected sector allocation weight assuming equal split of current positions + 1
            projected_count = sector_counts[sec] + 1
            # If total max positions is N, projected weight is projected_count / max(1, N)
            projected_sector_weight = projected_count * config.min_weight_per_asset
            if projected_sector_weight > config.max_sector_exposure and sector_counts[sec] > 0:
                logger.info(
                    "DiversificationEngine: Rejecting '%s' (sector '%s' count %d exceeds exposure cap %.2f)",
                    candidate.symbol,
                    sec,
                    projected_count,
                    config.max_sector_exposure,
                )
                rejected_symbols.append(candidate.symbol)
                continue

            accepted.append(candidate)
            sector_counts[sec] += 1

        return accepted, rejected_symbols
