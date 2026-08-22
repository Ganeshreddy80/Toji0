"""PnL tracker updating realized and unrealized asset return metrics.
"""

from __future__ import annotations

import logging
from typing import Dict, List
from research_platform.paper_trading.models import PaperPosition

logger = logging.getLogger(__name__)


class PnlTracker:
    """Calculates strategy return metrics on position updates."""

    def update_unrealized_pnl(self, positions: List[PaperPosition], current_prices: Dict[str, float]) -> List[PaperPosition]:
        updated_positions = []
        for pos in positions:
            curr_price = current_prices.get(pos.symbol, pos.current_price)
            unrealized = 0.0
            if pos.quantity != 0.0:
                unrealized = pos.quantity * (curr_price - pos.entry_price)

            updated = pos.model_copy(update={
                "current_price": curr_price,
                "unrealized_pnl": unrealized
            })
            updated_positions.append(updated)
        return updated_positions
