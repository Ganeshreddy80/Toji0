"""Attribution engine performing multi-dimension attributions across strategies, symbols, regimes.
"""

from __future__ import annotations

from typing import Any, Dict, List
from research_platform.portfolio_analytics.interfaces import IAttributionEngine
from research_platform.portfolio_analytics.models import StrategyAttribution


class AttributionEngine(IAttributionEngine):
    """Calculates risk contributions and returns attributions across strategies and regimes."""

    def attribute_performance(self, trades: List[Any], total_pnl: float) -> List[StrategyAttribution]:
        if not trades:
            return []

        # Aggregate PnL per strategy
        strat_pnl: Dict[str, float] = {}
        for trade in trades:
            s_id = getattr(trade, "strategy_id", "default")
            pnl = getattr(trade, "pnl", 0.0)
            strat_pnl[s_id] = strat_pnl.get(s_id, 0.0) + pnl

        attributions: List[StrategyAttribution] = []
        total_pnl_abs = sum(abs(p) for p in strat_pnl.values())
        
        for s_id, pnl in strat_pnl.items():
            alloc_pct = 1.0 / len(strat_pnl)
            contr_pct = pnl / total_pnl if total_pnl != 0.0 else 0.0
            risk_pct = abs(pnl) / total_pnl_abs if total_pnl_abs > 0.0 else 0.0

            attributions.append(StrategyAttribution(
                strategy_id=s_id,
                allocation_pct=alloc_pct,
                contribution_pnl=pnl,
                risk_contribution_pct=risk_pct
            ))

        return attributions
