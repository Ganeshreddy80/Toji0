"""Virtual Paper Broker simulating order execution without external exchange connectivity (Sprint 9A)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional, Tuple

from paper_trading.events import (
    PaperAccountUpdated,
    PaperOrderCancelled,
    PaperOrderFilled,
    PaperOrderSubmitted,
    PaperPositionUpdated,
    PaperTradeExecuted,
)
from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperTrade,
)
from paper_trading.orders import PaperOrderEngine
from paper_trading.portfolio import PaperPortfolio
from paper_trading.repository import PaperRepository
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class PaperBroker:
    """Virtual Broker simulating order execution, validation, and fill matching.

    MUST NEVER connect to live exchanges, send broker API requests, or execute real trades.
    """

    def __init__(
        self,
        portfolio: Optional[PaperPortfolio] = None,
        order_engine: Optional[PaperOrderEngine] = None,
        repository: Optional[PaperRepository] = None,
        event_bus: Optional[IEventBus] = None,
        commission_rate: float = 0.001,
    ) -> None:
        self._lock = threading.RLock()
        self._portfolio = portfolio or PaperPortfolio()
        self._order_engine = order_engine or PaperOrderEngine()
        self._repository = repository or PaperRepository()
        self._event_bus = event_bus
        self._commission_rate = commission_rate

        self._pending_orders: List[PaperOrder] = []
        self._market_prices: Dict[str, float] = {}

    def submit_order(
        self,
        symbol: str,
        side: PaperOrderSide,
        quantity: float,
        order_type: PaperOrderType = PaperOrderType.MARKET,
        limit_price: float = 0.0,
        stop_price: float = 0.0,
        current_market_price: Optional[float] = None,
        order_id: Optional[str] = None,
    ) -> Tuple[PaperOrder, List[PaperTrade]]:
        """Submit and validate a new paper order for execution simulation.

        Returns updated PaperOrder and list of executed PaperTrade fills.
        """
        with self._lock:
            # 1. Create Order
            order = self._order_engine.create_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                order_id=order_id,
            )

            mkt_price = current_market_price or self._market_prices.get(symbol, 0.0)

            # 2. Validate Buying Power / Cash for BUY orders (LIMIT, MARKET, STOP)
            if not self._portfolio.reserve_cash_for_order(order, market_price=mkt_price):
                rejected_order = self._order_engine.update_order_status(order.order_id, PaperOrderStatus.REJECTED)
                self._repository.save_order(rejected_order)
                return rejected_order, []

            # Transition status to PENDING
            pending_order = self._order_engine.update_order_status(order.order_id, PaperOrderStatus.PENDING)
            self._repository.save_order(pending_order)

            # Publish PaperOrderSubmitted
            if self._event_bus:
                self._event_bus.publish(PaperOrderSubmitted(order=pending_order))

            # 3. Simulate Immediate Fill for MARKET orders if market_price > 0
            if order_type == PaperOrderType.MARKET and mkt_price > 0.0:
                return self._execute_fill(pending_order, fill_price=mkt_price, fill_qty=quantity)

            # Check immediate limit/stop triggers if market_price > 0
            if mkt_price > 0.0:
                should_fill, fill_p = self._check_fill_condition(pending_order, mkt_price)
                if should_fill:
                    return self._execute_fill(pending_order, fill_price=fill_p, fill_qty=quantity)

            # Register as pending order for future market ticks
            self._pending_orders.append(pending_order)
            return pending_order, []

    def cancel_order(self, order_id: str) -> PaperOrder:
        """Cancel an active pending paper order."""
        with self._lock:
            cancelled_order = self._order_engine.cancel_order(order_id)
            self._portfolio.release_reserved_cash(cancelled_order)
            self._repository.save_order(cancelled_order)

            # Remove from pending list
            self._pending_orders = [o for o in self._pending_orders if o.order_id != order_id]

            if self._event_bus:
                self._event_bus.publish(PaperOrderCancelled(order=cancelled_order))

            return cancelled_order

    def on_market_tick(self, symbol: str, price: float) -> List[Tuple[PaperOrder, PaperTrade]]:
        """Process real-time market price tick, evaluate pending limit/stop orders, and execute fills."""
        if price <= 0.0:
            return []

        with self._lock:
            self._market_prices[symbol] = price
            # Update mark-to-market prices in portfolio
            pos = self._portfolio.update_market_price(symbol, price)
            if pos and self._event_bus:
                self._event_bus.publish(PaperPositionUpdated(position=pos))

            account_snapshot = self._portfolio.get_account_snapshot()
            self._repository.save_account(account_snapshot)

            executed_pairs: List[Tuple[PaperOrder, PaperTrade]] = []
            remaining_pending: List[PaperOrder] = []

            for order in list(self._pending_orders):
                if order.symbol != symbol:
                    remaining_pending.append(order)
                    continue

                should_fill, fill_p = self._check_fill_condition(order, price)
                if should_fill:
                    fill_qty = order.quantity - order.filled_quantity
                    updated_order, trades = self._execute_fill(order, fill_price=fill_p, fill_qty=fill_qty)
                    if trades:
                        executed_pairs.append((updated_order, trades[0]))
                else:
                    remaining_pending.append(order)

            self._pending_orders = remaining_pending
            return executed_pairs

    def _check_fill_condition(self, order: PaperOrder, market_price: float) -> Tuple[bool, float]:
        """Evaluate if market_price triggers fill condition for limit or stop order."""
        if order.order_type == PaperOrderType.MARKET:
            return True, market_price

        if order.order_type == PaperOrderType.LIMIT:
            if order.side in (PaperOrderSide.BUY, PaperOrderSide.LONG):
                if market_price <= order.limit_price:
                    return True, min(market_price, order.limit_price)
            else:  # SELL / SHORT
                if market_price >= order.limit_price:
                    return True, max(market_price, order.limit_price)

        if order.order_type == PaperOrderType.STOP:
            if order.side in (PaperOrderSide.BUY, PaperOrderSide.LONG):
                if market_price >= order.stop_price:
                    return True, market_price
            else:  # SELL / SHORT
                if market_price <= order.stop_price:
                    return True, market_price

        return False, 0.0

    def _execute_fill(
        self,
        order: PaperOrder,
        fill_price: float,
        fill_qty: float,
    ) -> Tuple[PaperOrder, List[PaperTrade]]:
        """Internal helper executing fill simulation, portfolio update, repository save, and event publishing."""
        comm = fill_qty * fill_price * self._commission_rate
        trade = PaperTrade(
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=fill_qty,
            fill_price=fill_price,
            commission=comm,
        )

        new_filled_qty = order.filled_quantity + fill_qty
        new_status = PaperOrderStatus.FILLED if new_filled_qty >= order.quantity else PaperOrderStatus.PARTIALLY_FILLED
        new_avg_price = (
            (order.filled_quantity * order.average_fill_price + fill_qty * fill_price) / new_filled_qty
            if new_filled_qty > 0
            else fill_price
        )

        updated_order = self._order_engine.update_order_status(
            order_id=order.order_id,
            new_status=new_status,
            filled_qty=new_filled_qty,
            avg_fill_price=new_avg_price,
        )

        # Apply fill to portfolio
        account_snapshot, updated_position = self._portfolio.apply_fill(updated_order, trade)

        # Save to repository
        self._repository.save_order(updated_order)
        self._repository.save_trade(trade)
        self._repository.save_account(account_snapshot)
        if updated_position:
            self._repository.save_position(updated_position)

        # Publish Events
        if self._event_bus:
            self._event_bus.publish(PaperTradeExecuted(trade=trade))
            self._event_bus.publish(PaperOrderFilled(order=updated_order, trade=trade))
            self._event_bus.publish(PaperAccountUpdated(account=account_snapshot))
            if updated_position:
                self._event_bus.publish(PaperPositionUpdated(position=updated_position))

        return updated_order, [trade]
