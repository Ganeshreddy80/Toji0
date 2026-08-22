"""Fill Engine — bid/ask spread, maker/taker fees, partial fills, and final PnL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from research_platform.execution_engine.simulator_models import (
    OrderStatus,
    SimulatedFill,
)
from research_platform.execution_engine.slippage import SlippageEngine
from research_platform.execution_engine.liquidity import LiquidityEngine


class FillEngine:
    """Simulates realistic order fills including spread, fees, slippage, and partial fills.

    Spread model:
        bid = price - spread / 2
        ask = price + spread / 2

    Market orders execute at ask (BUY) or bid (SELL).
    Limit orders execute at limit_price if the market moves through it.
    """

    DEFAULT_SPREAD_BPS: float = 6.0     # 0.06 % round-trip
    MAKER_FEE: float = 0.0002           # 0.02 %
    TAKER_FEE: float = 0.0005           # 0.05 %
    PARTIAL_FILL_THRESHOLD: float = 0.50  # fills <50 % of qty on thin liquidity

    def __init__(
        self,
        spread_bps: float = DEFAULT_SPREAD_BPS,
        maker_fee: float = MAKER_FEE,
        taker_fee: float = TAKER_FEE,
        max_volume_pct: float = 0.20,
    ) -> None:
        self.spread_bps = spread_bps
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self._slippage_engine = SlippageEngine()
        self._liquidity_engine = LiquidityEngine(max_volume_pct=max_volume_pct)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fill_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        mid_price: float,
        market_volume: float,
        atr: float,
        expected_entry: float,
        order_id: Optional[str] = None,
    ) -> SimulatedFill:
        """Simulate a market order fill with slippage and taker fees."""
        order_id = order_id or str(uuid.uuid4())

        # Liquidity gate
        liq = self._liquidity_engine.check_liquidity(quantity, market_volume)
        if not liq.passed:
            return self._rejected_fill(order_id, symbol, side, mid_price, quantity, liq.reason)

        # Spread → execution side price
        half_spread = mid_price * (self.spread_bps / 20_000.0)
        exec_price = mid_price + half_spread if side.upper() == "BUY" else mid_price - half_spread

        # Slippage on top of spread
        slip = self._slippage_engine.calculate_slippage(
            price=exec_price,
            order_qty=quantity,
            market_volume=market_volume,
            atr=atr,
            side=side,
        )
        fill_price = slip["fill_price"]

        # Taker fee (market orders always take liquidity)
        fee_paid = fill_price * quantity * self.taker_fee
        notional = fill_price * quantity
        pnl_before_fee = (fill_price - expected_entry) * quantity if side.upper() == "BUY" else (expected_entry - fill_price) * quantity
        after_fee_pnl = pnl_before_fee - fee_paid

        return SimulatedFill(
            order_id=order_id,
            symbol=symbol,
            side=side.upper(),
            expected_price=expected_entry,
            fill_price=fill_price,
            quantity=quantity,
            quantity_filled=quantity,
            status=OrderStatus.FILLED,
            maker_fee=self.maker_fee,
            taker_fee=self.taker_fee,
            fee_paid=round(fee_paid, 4),
            slippage=slip["slippage_abs"],
            slippage_cost=slip["slippage_cost"],
            after_fee_pnl=round(after_fee_pnl, 4),
            notes="market_order",
        )

    def fill_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float,
        current_market_price: float,
        market_volume: float,
        atr: float,
        expected_entry: float,
        order_id: Optional[str] = None,
    ) -> SimulatedFill:
        """Simulate a limit order fill.

        Filled only when current_market_price <= limit for BUY
        or current_market_price >= limit for SELL.
        Uses maker fees (passive liquidity provision).
        Simulates partial fills when volume < order size.
        """
        order_id = order_id or str(uuid.uuid4())

        # Price check — is the limit reachable?
        if side.upper() == "BUY" and current_market_price > limit_price:
            return self._rejected_fill(
                order_id, symbol, side, limit_price, quantity,
                f"Limit {limit_price} not reached (market {current_market_price})"
            )
        if side.upper() == "SELL" and current_market_price < limit_price:
            return self._rejected_fill(
                order_id, symbol, side, limit_price, quantity,
                f"Limit {limit_price} not reached (market {current_market_price})"
            )

        # Partial fill simulation: thin liquidity → partial
        liq = self._liquidity_engine.check_liquidity(quantity, market_volume)
        if not liq.passed:
            qty_filled = quantity * self.PARTIAL_FILL_THRESHOLD
            status = OrderStatus.PARTIAL_FILLED
            note = "partial_fill_thin_liquidity"
        else:
            qty_filled = quantity
            status = OrderStatus.FILLED
            note = "limit_order"

        fill_price = limit_price  # limit fills at requested price (no slippage for passive)
        fee_paid = fill_price * qty_filled * self.maker_fee
        pnl_before_fee = (fill_price - expected_entry) * qty_filled if side.upper() == "BUY" else (expected_entry - fill_price) * qty_filled
        after_fee_pnl = pnl_before_fee - fee_paid

        return SimulatedFill(
            order_id=order_id,
            symbol=symbol,
            side=side.upper(),
            expected_price=expected_entry,
            fill_price=fill_price,
            quantity=quantity,
            quantity_filled=qty_filled,
            status=status,
            maker_fee=self.maker_fee,
            taker_fee=self.taker_fee,
            fee_paid=round(fee_paid, 4),
            slippage=0.0,
            slippage_cost=0.0,
            after_fee_pnl=round(after_fee_pnl, 4),
            notes=note,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rejected_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        reason: str,
    ) -> SimulatedFill:
        return SimulatedFill(
            order_id=order_id,
            symbol=symbol,
            side=side.upper(),
            expected_price=price,
            fill_price=price,
            quantity=quantity,
            quantity_filled=0.0,
            status=OrderStatus.REJECTED,
            maker_fee=self.maker_fee,
            taker_fee=self.taker_fee,
            fee_paid=0.0,
            slippage=0.0,
            slippage_cost=0.0,
            after_fee_pnl=0.0,
            notes=reason,
        )
