"""Risk parity allocation engine sizing based on inverse volatility.
"""

from __future__ import annotations

from typing import Dict, List


class RiskParityEngine:
    """Sizes weights inversely proportional to asset volatilities."""

    def calculate_risk_parity(self, assets: List[str], volatilities: Dict[str, float]) -> Dict[str, float]:
        if not assets:
            return {}

        inv_vols = {}
        for a in assets:
            vol = volatilities.get(a, 0.20)  # Default 20% vol if missing
            inv_vols[a] = 1.0 / max(0.01, vol)

        total_inv = sum(inv_vols.values())
        return {a: val / total_inv for a, val in inv_vols.items()}
