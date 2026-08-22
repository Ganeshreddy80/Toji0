"""Exposure engine checking sector and asset concentration boundaries.
"""

from __future__ import annotations

from typing import Dict


class ExposureEngine:
    """Checks allocation weights against maximum limits."""

    def check_exposure_limits(
        self,
        weights: Dict[str, float],
        max_asset_limit: float = 0.25
    ) -> Dict[str, float]:
        clipped = {}
        for asset, w in weights.items():
            clipped[asset] = min(max_asset_limit, w)

        return clipped
