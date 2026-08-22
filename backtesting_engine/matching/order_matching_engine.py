"""Deterministic order matching engine for MARKET, LIMIT, STOP, STOP_LIMIT, IOC, and FOK orders (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import List, Optional

from backtesting_engine.core.enums import (
    OrderType,
    PositionSide,
    SimulatedOrderStatus,
    TimeInForce,
)
from backtesting_engine.core.events import OrderMatched
from backtesting_engine.core.exceptions import OrderMatchingError
from backtesting_engine.core.interfaces import IOrderMatchingEngine
from backtesting_engine.core.models import (
    BacktestConfig,
    MarketBar,
    SimulatedFill,
    SimulatedOrder,
)
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


from backtesting_engine.matching.execution_realism import (
    CommissionEngine,
    LiquidityEngine,
    MarketImpactEngine,
    SlippageEngine,
    SpreadEngine,
)


class OrderMatchingEngine(IOrderMatchingEngine):
    """Matches open orders deterministically against replayed OHLCV market bars without randomness."""

    def __init__(self, event_bus: Optional[IEventBus] = None) -> None:
        self._event_bus = event_bus

    def match_orders(
        self,
        orders: List[SimulatedOrder],
        bar: MarketBar,
        config: BacktestConfig,
        liquidity_engine: Optional[LiquidityEngine] = None,
    ) -> List[SimulatedFill]:
        """Match active open orders against replayed market bar and return generated fills in FIFO queue priority."""
        if not bar or bar.close <= 0.0:
            raise OrderMatchingError("Invalid market bar provided for order matching.")

        # 5. Queue Priority: Stable sorting by created_at (FIFO deterministic ordering)
        sorted_orders = sorted(orders, key=lambda o: o.created_at)
        quote = SpreadEngine.calculate_quote(bar, config)
        fills: List[SimulatedFill] = []

        for order in sorted_orders:
            if order.symbol != bar.symbol or order.status in (
                SimulatedOrderStatus.FILLED,
                SimulatedOrderStatus.CANCELLED,
                SimulatedOrderStatus.REJECTED,
            ):
                continue

            fill = self._match_single_order(order, bar, config, quote, liquidity_engine)
            if fill:
                fills.append(fill)
                if self._event_bus:
                    self._event_bus.publish(
                        OrderMatched(
                            source="backtesting.matching",
                            payload={
                                "fill_id": fill.fill_id,
                                "order_id": fill.order_id,
                                "symbol": fill.symbol,
                                "side": fill.side.value,
                                "quantity": fill.fill_quantity,
                                "price": fill.fill_price,
                                "fee": fill.fee,
                            },
                        )
                    )

        return fills

    def _match_single_order(
        self,
        order: SimulatedOrder,
        bar: MarketBar,
        config: BacktestConfig,
        quote: SyntheticQuote,
        liquidity_engine: Optional[LiquidityEngine] = None,
    ) -> Optional[SimulatedFill]:
        """Evaluate matching conditions for a single order against bar OHLCV range and synthetic quotes."""
        remaining_qty = order.quantity - order.filled_quantity
        if remaining_qty <= 0.0:
            return None

        # 3. Liquidity Model: Volume capping
        if liquidity_engine:
            allocated_qty, _ = liquidity_engine.allocate_fill_quantity(remaining_qty)
        else:
            if bar.volume > 0.0 and config.max_volume_pct < 1.0:
                max_bar_vol = bar.volume * config.max_volume_pct
                allocated_qty = min(remaining_qty, max_bar_vol)
            else:
                allocated_qty = remaining_qty

        if allocated_qty <= 0.0:
            return None

        matched_price: Optional[float] = None

        # 2. Spread Simulation & Trigger evaluation
        if order.order_type == OrderType.MARKET:
            m_base = bar.open if bar.open > 0.0 else bar.close
            m_quote = SpreadEngine.calculate_quote(bar, config, base_price=m_base)
            matched_price = m_quote.ask if order.side == PositionSide.LONG else m_quote.bid

        elif order.order_type == OrderType.LIMIT:
            if order.side == PositionSide.LONG:
                if bar.low <= order.price:
                    base_p = min(bar.open, order.price)
                    l_quote = SpreadEngine.calculate_quote(bar, config, base_price=base_p)
                    matched_price = l_quote.ask
            else:  # SHORT
                if bar.high >= order.price:
                    base_p = max(bar.open, order.price)
                    l_quote = SpreadEngine.calculate_quote(bar, config, base_price=base_p)
                    matched_price = l_quote.bid

        elif order.order_type == OrderType.STOP:
            if order.side == PositionSide.LONG:
                if bar.high >= order.stop_price:
                    base_p = max(bar.open, order.stop_price)
                    s_quote = SpreadEngine.calculate_quote(bar, config, base_price=base_p)
                    matched_price = s_quote.ask
            else:  # SHORT
                if bar.low <= order.stop_price:
                    base_p = min(bar.open, order.stop_price)
                    s_quote = SpreadEngine.calculate_quote(bar, config, base_price=base_p)
                    matched_price = s_quote.bid

        elif order.order_type == OrderType.STOP_LIMIT:
            stop_triggered = (
                bar.high >= order.stop_price if order.side == PositionSide.LONG else bar.low <= order.stop_price
            )
            if stop_triggered:
                if order.side == PositionSide.LONG and bar.low <= order.price:
                    base_p = min(bar.open, order.price)
                    sl_quote = SpreadEngine.calculate_quote(bar, config, base_price=base_p)
                    matched_price = sl_quote.ask
                elif order.side == PositionSide.SHORT and bar.high >= order.price:
                    base_p = max(bar.open, order.price)
                    sl_quote = SpreadEngine.calculate_quote(bar, config, base_price=base_p)
                    matched_price = sl_quote.bid

        if matched_price is None:
            return None

        # Enforce FOK fill constraint: partial fills are strictly forbidden for FOK orders
        if order.time_in_force == TimeInForce.FOK and allocated_qty < remaining_qty:
            return None

        # 9. Market Impact Engine
        impact_adj = MarketImpactEngine.calculate_impact(matched_price, order.side, allocated_qty, bar, config)
        base_with_impact = matched_price + impact_adj

        # 1. Slippage Engine
        executed_price, applied_slippage = SlippageEngine.calculate_slippage(base_with_impact, order.side, allocated_qty, bar, config, quote)

        # Round precision
        executed_price = round(executed_price, config.tick_precision)
        matched_qty = round(allocated_qty, config.lot_precision)

        if matched_qty <= 0.0 or executed_price <= 0.0:
            return None

        # 7. Commission Engine
        fee = CommissionEngine.calculate_fee(matched_qty, executed_price, order.order_type, config)

        return SimulatedFill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            fill_quantity=matched_qty,
            fill_price=executed_price,
            fee=fee,
            slippage=applied_slippage,
            timestamp=bar.timestamp,
        )
