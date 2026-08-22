"""Exchange simulator matching paper orders against market pricing parameters.
"""

from __future__ import annotations

import logging
from research_platform.paper_trading.interfaces import IPaperExchange
from research_platform.paper_trading.models import PaperOrder

logger = logging.getLogger(__name__)


class PaperExchange(IPaperExchange):
    """Simulates market matching operations inside the sandbox."""

    def match_order(self, order: PaperOrder, price: float, spread: float) -> PaperOrder:
        """Match paper order details against target market pricing parameters."""
        if order.status != "PENDING":
            return order

        # MARKET Order fills immediately with half-spread slippage penalty
        if order.order_type == "MARKET":
            slippage = spread / 2.0
            fill_price = price + slippage if order.side == "BUY" else price - slippage
            logger.info("Paper MARKET order '%s' filled at %.4f", order.order_id, fill_price)
            return order.model_copy(update={
                "status": "FILLED",
                "executed_price": fill_price,
                "executed_quantity": order.quantity
            })

        # LIMIT Order matches if the ask/bid bounds cross the limit price
        elif order.order_type == "LIMIT":
            if order.side == "BUY":
                ask_price = price + (spread / 2.0)
                if ask_price <= order.price:
                    logger.info("Paper LIMIT BUY order '%s' filled at %.4f", order.order_id, order.price)
                    return order.model_copy(update={
                        "status": "FILLED",
                        "executed_price": order.price,
                        "executed_quantity": order.quantity
                    })
            else:
                bid_price = price - (spread / 2.0)
                if bid_price >= order.price:
                    logger.info("Paper LIMIT SELL order '%s' filled at %.4f", order.order_id, order.price)
                    return order.model_copy(update={
                        "status": "FILLED",
                        "executed_price": order.price,
                        "executed_quantity": order.quantity
                    })

        return order
