"""Position sizer calculating equal weights allocations.
"""

from __future__ import annotations

from typing import Dict, List


class PositionSizer:
    """Sizes positions equally across list of active symbols."""

    def size_equally(self, assets: List[str]) -> Dict[str, float]:
        if not assets:
            return {}
        weight = 1.0 / len(assets)
        return {asset: weight for asset in assets}
