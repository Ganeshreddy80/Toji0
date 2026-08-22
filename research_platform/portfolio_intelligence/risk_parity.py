"""Risk Parity equal-risk contribution asset allocation."""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class RiskParityAllocator:
    """Calculates risk parity weights proportional to the inverse of asset volatilities."""

    def calculate_weights(self, assets_volatility: Dict[str, float]) -> Dict[str, float]:
        """Assigns weights inversely proportional to volatilities.

        Weight_i = (1 / Vol_i) / Sum(1 / Vol_j)
        """
        if not assets_volatility:
            return {}

        # Handle zero or negative values
        clean_vols = {}
        for asset, vol in assets_volatility.items():
            if vol > 0.0:
                clean_vols[asset] = vol
            else:
                clean_vols[asset] = 0.01  # Fallback to tiny volatility

        # Compute inverse volatilities
        inv_vols = {asset: 1.0 / vol for asset, vol in clean_vols.items()}
        sum_inv = sum(inv_vols.values())

        if sum_inv <= 0.0:
            # Equal weight fallback
            equal_val = 1.0 / len(assets_volatility)
            return {asset: equal_val for asset in assets_volatility}

        # Normalize weights to sum to 1.0
        return {asset: inv / sum_inv for asset, inv in inv_vols.items()}
