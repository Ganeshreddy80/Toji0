"""Correlation filtering engine for Portfolio Construction."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from portfolio_construction.core.interfaces import ICorrelationFilter
from portfolio_construction.core.models import PortfolioCandidate

logger = logging.getLogger(__name__)


class CorrelationFilter(ICorrelationFilter):
    """Filters portfolio candidate setups exceeding pairwise correlation limits."""

    def filter_candidates(
        self,
        candidates: List[PortfolioCandidate],
        correlation_matrix: Dict[str, Dict[str, float]],
        max_correlation: float,
    ) -> Tuple[List[PortfolioCandidate], List[str]]:
        """
        Filter candidate setups exceeding pairwise correlation thresholds.
        Higher confidence candidates are prioritized; highly correlated candidates are rejected.
        """
        if not candidates:
            return [], []

        # Sort candidates by confidence descending
        sorted_candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)

        accepted: List[PortfolioCandidate] = []
        rejected_symbols: List[str] = []

        for candidate in sorted_candidates:
            sym = candidate.symbol
            too_correlated = False

            for acc in accepted:
                acc_sym = acc.symbol
                # Lookup pairwise correlation
                corr = 0.0
                if correlation_matrix and sym in correlation_matrix:
                    corr = correlation_matrix[sym].get(acc_sym, 0.0)
                elif correlation_matrix and acc_sym in correlation_matrix:
                    corr = correlation_matrix[acc_sym].get(sym, 0.0)

                if abs(corr) > max_correlation:
                    logger.info(
                        "CorrelationFilter: Rejecting '%s' (corr=%.2f with '%s' > max_corr=%.2f)",
                        sym,
                        corr,
                        acc_sym,
                        max_correlation,
                    )
                    too_correlated = True
                    break

            if too_correlated:
                rejected_symbols.append(sym)
            else:
                accepted.append(candidate)

        return accepted, rejected_symbols
