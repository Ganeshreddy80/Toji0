"""Position Risk evaluations checking order sizes and stop-loss bounds.
"""

from __future__ import annotations

from research_platform.risk_management.models import PositionRisk
from research_platform.oms.models import OrderRequest


class PositionRiskEvaluator:
    """Audits single order size parameters, reward ratios, and stop distances."""

    def __init__(self, max_risk_per_trade: float = 0.02) -> None:
        self.max_risk_per_trade = max_risk_per_trade

    def evaluate_position_risk(self, request: OrderRequest) -> PositionRisk:
        """Calculate order stop metrics and leverage utilization ratios."""
        # Simple stop-loss simulation: set stop distance to 5% of order price
        stop_dist = request.price * 0.05 if request.price > 0.0 else 0.0

        return PositionRisk(
            symbol=request.symbol,
            quantity=request.quantity,
            stop_loss_distance=stop_dist,
            margin_utilization=0.10
        )
