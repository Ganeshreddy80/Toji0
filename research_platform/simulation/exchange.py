"""Exchange order-matching and latency simulator engine implementing IExchangeSimulator.
"""

from __future__ import annotations

import logging
from research_platform.simulation.interfaces import IExchangeSimulator
from research_platform.simulation.models import SimOrder, SimTick, StressParameters

logger = logging.getLogger(__name__)


class ExchangeSimulator(IExchangeSimulator):
    """Simulates order matching, spreads slippages, delayed latency, and failures."""

    def match_order(self, order: SimOrder, tick: SimTick) -> SimOrder:
        """Fallback without stress params using default constraints."""
        return self.match_order_with_stress(order, tick, StressParameters())

    def match_order_with_stress(self, order: SimOrder, tick: SimTick, stress: StressParameters) -> SimOrder:
        """Match SimOrder against price feed ticks incorporating spread and network latency delay stressors."""
        if order.status != "PENDING":
            return order

        # Network latency delay mock logging
        if stress.network_latency_ms > 0:
            logger.debug("Simulated network delay: %.2f ms", stress.network_latency_ms)

        adjusted_spread = tick.spread * stress.spread_scale

        # 1. MARKET Orders match immediately with half-spread slippage penalty
        if order.order_type == "MARKET":
            slippage = adjusted_spread / 2.0
            fill_price = tick.price + slippage if order.side == "BUY" else tick.price - slippage
            
            logger.info("MARKET order '%s' filled at %.4f (Slippage: %.4f)", order.order_id, fill_price, slippage)
            return order.model_copy(update={
                "status": "FILLED",
                "price": fill_price
            })

        # 2. LIMIT Orders match when price passes target limits bounds
        elif order.order_type == "LIMIT":
            if order.side == "BUY":
                # Buy limit fills if market ask price is lower or equal to limit price
                ask_price = tick.price + (adjusted_spread / 2.0)
                if ask_price <= order.price:
                    logger.info("LIMIT BUY order '%s' filled at %.4f", order.order_id, order.price)
                    return order.model_copy(update={"status": "FILLED"})
            else:
                # Sell limit fills if market bid price is higher or equal to limit price
                bid_price = tick.price - (adjusted_spread / 2.0)
                if bid_price >= order.price:
                    logger.info("LIMIT SELL order '%s' filled at %.4f", order.order_id, order.price)
                    return order.model_copy(update={"status": "FILLED"})

        # Remain pending if not matched
        return order
