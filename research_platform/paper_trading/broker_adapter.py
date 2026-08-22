"""Broker adapter translating paper orders into exchange matches.
"""

from __future__ import annotations

import logging
from research_platform.paper_trading.interfaces import IPaperBrokerAdapter
from research_platform.paper_trading.models import PaperAccount, PaperOrder
from research_platform.paper_trading.paper_exchange import PaperExchange

logger = logging.getLogger(__name__)


class PaperBrokerAdapter(IPaperBrokerAdapter):
    """Calculates virtual transaction commissions and slippages."""

    def __init__(self, exchange: PaperExchange) -> None:
        self._exchange = exchange

    def execute_order(self, account: PaperAccount, order: PaperOrder) -> PaperOrder:
        """Process paper order, calculate commission fees and return filled order."""
        # For simplicity, if we directly execute a market order under mock context:
        price = order.price if order.price > 0.0 else 100.0
        spread = 0.02
        
        updated_order = self._exchange.match_order(order, price, spread)
        return updated_order
