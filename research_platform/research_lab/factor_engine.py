"""Factor engine computing pricing factors formulas.
"""

from __future__ import annotations

from typing import List
from research_platform.research_lab.interfaces import IFactorEngine
from research_platform.research_lab.models import AlphaFactor


class FactorEngine(IFactorEngine):
    """Calculates scaling factors from inputs based on formulas."""

    def calculate_factor(self, factor_id: str, formula: str, inputs: List[float]) -> AlphaFactor:
        # Enforce basic mathematical scaling calculations
        values = []
        if formula == "SCALE_5":
            values = [val * 5.0 for val in inputs]
        else:
            values = [val * 2.0 for val in inputs]

        return AlphaFactor(
            factor_id=factor_id,
            formula=formula,
            values=values
        )
