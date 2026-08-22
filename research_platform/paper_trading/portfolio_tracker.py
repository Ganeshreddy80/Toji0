"""Portfolio tracker monitoring net exposures and peak drawdowns.
"""

from __future__ import annotations

import logging
from research_platform.paper_trading.models import PaperAccount

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """Monitors virtual peak drawdowns and gross margin values."""

    def __init__(self) -> None:
        self._peak_equity = 0.0

    def calculate_drawdown(self, account: PaperAccount, open_positions_val: float) -> PaperAccount:
        equity = account.cash + open_positions_val
        if self._peak_equity == 0.0:
            self._peak_equity = max(account.initial_balance, equity)
            
        if equity > self._peak_equity:
            self._peak_equity = equity

        drawdown = 0.0
        if self._peak_equity > 0.0:
            drawdown = (self._peak_equity - equity) / self._peak_equity

        return account.model_copy(update={
            "equity": equity,
            "drawdown": drawdown
        })
