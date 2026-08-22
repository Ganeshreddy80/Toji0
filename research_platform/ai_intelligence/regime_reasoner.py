"""Market Regime Reasoner explaining market volatility trending structures.
"""

from __future__ import annotations

from research_platform.ai_intelligence.models import MarketContext


class MarketRegimeReasoner:
    """Uses price parameters statistics to reason trending sideways structures."""

    def reason_regime(self, volatility: float, trend_strength: float) -> MarketContext:
        """Categorize regime trending sideways statuses based on inputs."""
        regime = "SIDEWAYS"
        
        if trend_strength > 0.6:
            regime = "TRENDING"
        elif volatility > 0.4:
            regime = "VOLATILE"

        return MarketContext(
            regime_type=regime,
            volatility_score=volatility
        )
