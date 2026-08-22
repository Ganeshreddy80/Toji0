"""Context Builder gathering metrics context across subsystems.
"""

from __future__ import annotations

from typing import Any, Dict

from research_platform.ai_intelligence.interfaces import IAIContextBuilder


class AIContextBuilder(IAIContextBuilder):
    """Aggregates portfolio, risk, OMS, EMS, and latency metrics."""

    def gather_context(self) -> Dict[str, Any]:
        """Aggregate stats from risk limits, portfolio, OMS and EMS."""
        # Simple simulated gathering (DI handles resolver links)
        return {
            "portfolio_value": 100000.0,
            "net_exposure": 0.5,
            "var_utilization": 0.65,
            "open_alerts_count": 0,
            "system_healthy": True
        }
