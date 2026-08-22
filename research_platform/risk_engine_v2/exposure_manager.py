"""Portfolio exposure coordinator tracking sector limits and asset correlations."""

from __future__ import annotations

import logging
from typing import Dict, List, Any
import math

logger = logging.getLogger(__name__)


class PortfolioExposureManager:
    """Manages sector concentration limits, correlations, and drawdown bounds."""

    def __init__(self, sector_limits: Dict[str, float], max_drawdown_limit: float = 0.15) -> None:
        self.sector_limits = sector_limits
        self.max_drawdown_limit = max_drawdown_limit
        self.sector_exposure: Dict[str, float] = {}
        self.price_history: Dict[str, List[float]] = {}

    def update_exposure(self, sector: str, exposure_pct: float) -> None:
        self.sector_exposure[sector] = exposure_pct

    def check_sector_limits(self) -> List[str]:
        """Verify if any sector limits are currently breached."""
        violations = []
        for sector, limit in self.sector_limits.items():
            current = self.sector_exposure.get(sector, 0.0)
            if current > limit:
                violations.append(f"Sector '{sector}' exposure ({current}) exceeds limit ({limit})")
        return violations

    def record_price(self, symbol: str, price: float) -> None:
        self.price_history.setdefault(symbol, []).append(price)
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol].pop(0)

    def calculate_correlation_matrix(self) -> Dict[str, Any]:
        """Calculates Pearson correlation coefficients across tracked assets."""
        symbols = list(self.price_history.keys())
        n_symbols = len(symbols)
        if n_symbols < 2:
            return {"symbols": symbols, "matrix": []}

        matrix = [[1.0] * n_symbols for _ in range(n_symbols)]

        for i in range(n_symbols):
            for j in range(i + 1, n_symbols):
                s1, s2 = symbols[i], symbols[j]
                p1, p2 = self.price_history[s1], self.price_history[s2]
                
                # Align lengths
                min_len = min(len(p1), len(p2))
                if min_len < 3:
                    corr = 0.0
                else:
                    v1, v2 = p1[-min_len:], p2[-min_len:]
                    mean1 = sum(v1) / min_len
                    mean2 = sum(v2) / min_len
                    
                    num = sum((x - mean1) * (y - mean2) for x, y in zip(v1, v2))
                    den1 = sum((x - mean1) ** 2 for x in v1)
                    den2 = sum((y - mean2) ** 2 for y in v2)
                    
                    if den1 > 0 and den2 > 0:
                        corr = num / math.sqrt(den1 * den2)
                    else:
                        corr = 0.0
                
                matrix[i][j] = corr
                matrix[j][i] = corr

        return {
            "symbols": symbols,
            "matrix": matrix
        }
