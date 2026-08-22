"""Exposure Engine calculating asset and strategy concentration weights.
"""

from __future__ import annotations

from typing import Dict

from research_platform.risk_management.models import ExposureReport


class ExposureEngine:
    """Aggregates portfolio risk metrics to generate historical exposure snapshots."""

    def calculate_exposures(self, weights: Dict[str, float]) -> ExposureReport:
        """Sum total absolute weights exposure values."""
        total = sum(abs(w) for w in weights.values())
        return ExposureReport(
            total_exposure=total,
            sector_exposures={"CRPT": total}
        )
