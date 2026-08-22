"""Strategy Router to toggle active strategy rule modules based on detected market regime.
"""

from __future__ import annotations
from typing import Dict, Any, List

class StrategyRouter:
    """Routes execution signals to appropriate strategies based on active market regime."""

    def select_strategy(self, regime: str) -> str:
        """Determines the best strategy for the given regime.

        Regimes:
        - TRENDING: enable breakout strategy
        - RANGING: enable support/resistance bounce
        """
        regime_upper = regime.upper()
        if regime_upper == "TRENDING":
            return "EMA_BREAKOUT"
        elif regime_upper == "RANGING":
            return "SUPPORT_RESISTANCE_BOUNCE"
        elif regime_upper == "HIGH_VOLATILITY":
            return "VOLATILITY_GRID"
        elif regime_upper == "LOW_VOLATILITY":
            return "SCALPING"
        else:
            return "WAIT"

    def get_routing_rules(self, regime: str) -> Dict[str, Any]:
        """Returns details of enabled and disabled strategies for the regime."""
        regime_upper = regime.upper()
        if regime_upper == "TRENDING":
            return {
                "enabled": ["EMA_BREAKOUT", "TREND_FOLLOWING"],
                "disabled": ["SUPPORT_RESISTANCE_BOUNCE", "MEAN_REVERSION"]
            }
        elif regime_upper == "RANGING":
            return {
                "enabled": ["SUPPORT_RESISTANCE_BOUNCE", "MEAN_REVERSION"],
                "disabled": ["EMA_BREAKOUT", "TREND_FOLLOWING"]
            }
        else:
            return {
                "enabled": ["SCALPING"],
                "disabled": ["EMA_BREAKOUT", "SUPPORT_RESISTANCE_BOUNCE"]
            }
