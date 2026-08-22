"""Champion/Challenger evaluation engine comparing live and staging strategy performance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from research_platform.strategy_lifecycle.interfaces import IStrategyRepository

logger = logging.getLogger(__name__)


class ChampionChallengerEngine:
    """Manages performance comparisons and generates A/B comparison metrics logs."""

    def __init__(self, repository: IStrategyRepository) -> None:
        self._repo = repository

    def compare_strategies(
        self,
        champion_id: str,
        challenger_ids: List[str],
        metrics_overrides: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, Any]:
        """Perform performance comparisons using monitoring status or overrides. No auto-promotions."""
        comparison_results = {}

        # Resolve champion metrics
        champ_metrics = {"sharpe": 0.0, "drawdown": 1.0, "pnl": 0.0}
        if metrics_overrides and champion_id in metrics_overrides:
            champ_metrics = metrics_overrides[champion_id]
        else:
            champ_status = self._repo.get_monitoring_status(champion_id)
            if champ_status:
                champ_metrics = {
                    "sharpe": 0.0,  # Sharpe is usually not a real-time status metric, fallback to 0 or check parameters
                    "drawdown": champ_status.drawdown,
                    "pnl": champ_status.pnl
                }

        comparison_results[champion_id] = {
            "role": "CHAMPION",
            "metrics": champ_metrics
        }

        recommendations = []

        # Resolve challengers
        for chall_id in challenger_ids:
            chall_metrics = {"sharpe": 0.0, "drawdown": 1.0, "pnl": 0.0}
            if metrics_overrides and chall_id in metrics_overrides:
                chall_metrics = metrics_overrides[chall_id]
            else:
                chall_status = self._repo.get_monitoring_status(chall_id)
                if chall_status:
                    chall_metrics = {
                        "sharpe": 0.0,
                        "drawdown": chall_status.drawdown,
                        "pnl": chall_status.pnl
                    }

            comparison_results[chall_id] = {
                "role": "CHALLENGER",
                "metrics": chall_metrics
            }

            # Comparison evaluation rules (e.g. Challenger Sharpe exceeds Champion Sharpe)
            if chall_metrics.get("sharpe", 0) > champ_metrics.get("sharpe", 0):
                msg = f"Challenger '{chall_id}' Sharpe ({chall_metrics.get('sharpe')}) is better than Champion Sharpe ({champ_metrics.get('sharpe')})."
                recommendations.append(msg)
            elif chall_metrics.get("pnl", 0) > champ_metrics.get("pnl", 0) and chall_metrics.get("drawdown", 1.0) < champ_metrics.get("drawdown", 1.0):
                msg = f"Challenger '{chall_id}' has higher PnL and lower drawdown than Champion. Recommend manual governance review."
                recommendations.append(msg)

        report = {
            "comparison": comparison_results,
            "recommendations": recommendations,
            "status": "COMPLETED",
            "message": "Champion-challenger evaluation complete. Human review required for promotion decisions."
        }

        logger.info("Champion/Challenger evaluation complete for Champion '%s'", champion_id)
        return report
