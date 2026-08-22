"""Exposure balancer enforcing gross/net exposure bounds and concentration limits.
"""

from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ExposureBalancer:
    """Enforces gross/net exposure boundaries and asset concentration caps."""

    def balance_weights(
        self,
        weights: Dict[str, float],
        net_limit: float = 1.0,
        gross_limit: float = 1.5,
        concentration_limit: float = 0.4
    ) -> Dict[str, float]:
        """Verify weights compliance and adjust to satisfy bounds."""
        adjusted = dict(weights)

        # 1. Enforce concentration limit cap (e.g. max 40% in single asset)
        for s, w in adjusted.items():
            if abs(w) > concentration_limit:
                sign = 1.0 if w >= 0 else -1.0
                adjusted[s] = sign * concentration_limit

        # 2. Check gross exposure: sum(|w_i|)
        gross = sum(abs(w) for w in adjusted.values())
        if gross > gross_limit:
            scale = gross_limit / gross
            adjusted = {s: w * scale for s, w in adjusted.items()}

        # 3. Check net exposure: sum(w_i)
        net = sum(adjusted.values())
        if abs(net) > net_limit:
            scale = net_limit / abs(net)
            adjusted = {s: w * scale for s, w in adjusted.items()}

        return adjusted
