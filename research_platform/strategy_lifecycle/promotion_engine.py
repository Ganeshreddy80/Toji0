"""Promotion engine enforcing performance thresholds.
"""

from __future__ import annotations

from research_platform.strategy_lifecycle.interfaces import IPromotionEngine
from research_platform.strategy_lifecycle.models import StrategyStatus


class PromotionEngine(IPromotionEngine):
    """Verifies win rates, Sharpe ratios, and drawdowns before status promotions."""

    def evaluate_promotion(self, strategy: StrategyStatus) -> bool:
        stats = strategy.statistics
        
        # Enforce minimum thresholds checks
        if stats.trades_count < 10:
            return False
        if stats.sharpe_ratio < 1.5:
            return False
        if stats.max_drawdown > 0.15:
            return False
        if stats.win_rate < 0.40:
            return False
        if stats.paper_duration_days < 5.0:
            return False
            
        return True
