"""Account manager tracking virtual cash, equity, and margin levels.
"""

from __future__ import annotations

import logging
from research_platform.paper_trading.models import PaperAccount

logger = logging.getLogger(__name__)


class AccountManager:
    """Manages virtual balances and tracks margin requirements."""

    def update_balance_on_fill(self, account: PaperAccount, quantity: float, price: float, side: str, commission: float = 0.0) -> PaperAccount:
        cost = quantity * price
        fee = commission
        
        # BUY reduces cash, SELL increases cash
        if side == "BUY":
            new_cash = account.cash - cost - fee
        else:
            new_cash = account.cash + cost - fee

        new_equity = new_cash # will update with open positions valuation
        
        logger.info("Account '%s' update: Cash changed from %.2f to %.2f (Cost: %.2f)",
                    account.account_id, account.cash, new_cash, cost)

        return account.model_copy(update={
            "cash": new_cash,
            "equity": new_equity
        })
