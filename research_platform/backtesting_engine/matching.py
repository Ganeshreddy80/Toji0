"""Matching Engine for transaction execution simulation.
"""

from __future__ import annotations

import uuid
from typing import List

from research_platform.backtesting_engine.interfaces import IMatchingEngine
from research_platform.backtesting_engine.models import MarketEvent, Order, OrderFill


class MatchingEngine(IMatchingEngine):
    """Queue matching orders against pricing events."""

    def __init__(self, slippage_pct: float = 0.0005, commission_pct: float = 0.001) -> None:
        self._slippage_pct = slippage_pct
        self._commission_pct = commission_pct

    def match_orders(self, orders: List[Order], market_data: MarketEvent) -> List[OrderFill]:
        """Process and match pending orders against current market event prices."""
        fills = []
        close_price = market_data.data.get("close", 0.0)
        high = market_data.data.get("high", close_price)
        low = market_data.data.get("low", close_price)
        ask = market_data.data.get("ask", close_price)
        bid = market_data.data.get("bid", close_price)

        for order in orders:
            if order.status in ("FILLED", "REJECTED", "CANCELLED"):
                continue

            req = order.request
            fill_price = 0.0
            matched = False

            if req.order_type == "MARKET":
                # Market order matches immediately at best bid/ask or close price
                fill_price = ask if req.direction == "BUY" else bid
                matched = True

            elif req.order_type == "LIMIT":
                if req.direction == "BUY":
                    # Buy limit matches if low price <= limit price
                    if low <= req.price:
                        fill_price = min(req.price, ask)
                        matched = True
                elif req.direction == "SELL":
                    # Sell limit matches if high price >= limit price
                    if high >= req.price:
                        fill_price = max(req.price, bid)
                        matched = True

            elif req.order_type == "STOP":
                if req.direction == "BUY":
                    # Buy stop triggers if high price >= stop price
                    if high >= req.price:
                        fill_price = max(req.price, ask)
                        matched = True
                elif req.direction == "SELL":
                    # Sell stop triggers if low price <= stop price
                    if low <= req.price:
                        fill_price = min(req.price, bid)
                        matched = True

            if matched:
                # Apply simulated slippage
                slippage_val = fill_price * self._slippage_pct
                if req.direction == "BUY":
                    final_price = fill_price + slippage_val
                else:
                    final_price = fill_price - slippage_val

                # Calculate commission
                commission = final_price * req.quantity * self._commission_pct

                fills.append(
                    OrderFill(
                        order_id=order.order_id,
                        fill_id=str(uuid.uuid4()),
                        symbol=req.symbol,
                        quantity=req.quantity,
                        price=final_price,
                        commission=commission,
                        slippage=slippage_val,
                        timestamp=market_data.timestamp
                    )
                )

        return fills
