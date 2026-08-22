"""Paper Portfolio Engine managing cash ledger, positions, buying power, and PnL (Sprint 9A)."""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional, Tuple

from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperPosition,
    PaperTrade,
)

logger = logging.getLogger(__name__)


class PaperPortfolio:
    """Thread-safe portfolio engine managing positions, cash, buying power, and PnL."""

    def __init__(self, initial_capital: float = 100000.0) -> None:
        if initial_capital <= 0.0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")

        self._lock = threading.RLock()
        self._starting_cash = initial_capital
        self._available_cash = initial_capital
        self._reserved_cash = 0.0
        self._realized_pnl = 0.0

        self._positions: Dict[str, PaperPosition] = {}

    def get_account_snapshot(self) -> PaperAccount:
        """Compute and return current immutable PaperAccount snapshot."""
        with self._lock:
            total_unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())
            position_market_value = sum(p.market_value for p in self._positions.values())

            equity = self._available_cash + self._reserved_cash + position_market_value
            buying_power = max(0.0, self._available_cash)

            return PaperAccount(
                starting_cash=self._starting_cash,
                available_cash=self._available_cash,
                reserved_cash=self._reserved_cash,
                buying_power=buying_power,
                equity=equity,
                realized_pnl=self._realized_pnl,
                unrealized_pnl=total_unrealized_pnl,
            )

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get open position for symbol."""
        with self._lock:
            return self._positions.get(symbol)

    def get_all_positions(self) -> Dict[str, PaperPosition]:
        """Get all open positions dict."""
        with self._lock:
            return dict(self._positions)

    def reserve_cash_for_order(self, order: PaperOrder, market_price: float = 0.0) -> bool:
        """Validate and reserve cash for an open BUY order (LIMIT, MARKET, or STOP).

        Returns True if sufficient cash exists and reservation succeeded, False if insufficient cash.
        """
        with self._lock:
            if order.side in (PaperOrderSide.BUY, PaperOrderSide.LONG):
                est_price = (
                    order.limit_price
                    if order.limit_price > 0.0
                    else (order.stop_price if order.stop_price > 0.0 else market_price)
                )

                if est_price > 0.0:
                    required_cash = order.quantity * est_price
                    if self._available_cash < required_cash:
                        return False

                if order.limit_price > 0.0:
                    required_cash = order.quantity * order.limit_price
                    self._available_cash -= required_cash
                    self._reserved_cash += required_cash

            return True

    def release_reserved_cash(self, order: PaperOrder) -> None:
        """Release reserved cash when a BUY limit order is cancelled or rejected."""
        with self._lock:
            if order.side in (PaperOrderSide.BUY, PaperOrderSide.LONG) and order.limit_price > 0.0:
                unfilled_qty = order.quantity - order.filled_quantity
                if unfilled_qty > 0:
                    release_amount = unfilled_qty * order.limit_price
                    release_amount = min(release_amount, self._reserved_cash)
                    self._reserved_cash -= release_amount
                    self._available_cash += release_amount

    def update_market_price(self, symbol: str, price: float) -> Optional[PaperPosition]:
        """Update mark-to-market price for an asset and recalculate unrealized PnL."""
        if price <= 0.0:
            return None

        with self._lock:
            pos = self._positions.get(symbol)
            if not pos or abs(pos.quantity) < 1e-8:
                return None

            qty = pos.quantity
            avg_p = pos.average_price
            mkt_val = qty * price

            if qty > 0:  # Long
                unrealized = qty * (price - avg_p)
            else:  # Short
                unrealized = abs(qty) * (avg_p - price)

            updated_pos = PaperPosition(
                symbol=symbol,
                quantity=qty,
                average_price=avg_p,
                market_price=price,
                market_value=mkt_val,
                unrealized_pnl=unrealized,
                realized_pnl=pos.realized_pnl,
            )
            self._positions[symbol] = updated_pos
            return updated_pos

    def apply_fill(self, order: PaperOrder, trade: PaperTrade) -> Tuple[PaperAccount, Optional[PaperPosition]]:
        """Apply executed fill to portfolio, update cash ledger and position.

        Returns updated PaperAccount and PaperPosition snapshots.
        """
        with self._lock:
            symbol = trade.symbol
            qty = trade.quantity
            price = trade.fill_price
            comm = trade.commission
            side = order.side

            # 1. Adjust cash for limit order reservation vs fill cost
            if side in (PaperOrderSide.BUY, PaperOrderSide.LONG):
                if order.limit_price > 0.0:
                    # Release reserved cash corresponding to this fill amount
                    reserved_portion = qty * order.limit_price
                    reserved_portion = min(reserved_portion, self._reserved_cash)
                    self._reserved_cash -= reserved_portion
                    # Actual cost incurred
                    actual_cost = (qty * price) + comm
                    diff = reserved_portion - actual_cost
                    self._available_cash += diff
                else:
                    # Market/Stop order direct cash deduction
                    actual_cost = (qty * price) + comm
                    self._available_cash -= actual_cost
            else:  # SELL / SHORT
                proceeds = (qty * price) - comm
                self._available_cash += proceeds

            # Guarantee available_cash does not become negative due to precision issues
            self._available_cash = max(0.0, self._available_cash)

            # 2. Update Position
            existing = self._positions.get(symbol)
            old_qty = existing.quantity if existing else 0.0
            old_avg_p = existing.average_price if existing else 0.0
            old_realized = existing.realized_pnl if existing else 0.0

            realized_pnl_trade = 0.0

            if side in (PaperOrderSide.BUY, PaperOrderSide.LONG):
                if old_qty >= 0:
                    # Adding to Long position
                    new_qty = old_qty + qty
                    new_avg_p = (old_qty * old_avg_p + qty * price) / new_qty if new_qty > 0 else 0.0
                    new_realized = old_realized
                else:
                    # Closing Short position
                    cover_qty = min(qty, abs(old_qty))
                    realized_pnl_trade = cover_qty * (old_avg_p - price) - comm
                    self._realized_pnl += realized_pnl_trade
                    new_realized = old_realized + realized_pnl_trade

                    new_qty = old_qty + qty
                    if new_qty > 0:
                        new_avg_p = price
                    elif new_qty < 0:
                        new_avg_p = old_avg_p
                    else:
                        new_avg_p = 0.0
            else:  # SELL / SHORT
                if old_qty > 0:
                    # Closing Long position
                    close_qty = min(qty, old_qty)
                    realized_pnl_trade = close_qty * (price - old_avg_p) - comm
                    self._realized_pnl += realized_pnl_trade
                    new_realized = old_realized + realized_pnl_trade

                    new_qty = old_qty - qty
                    if new_qty < 0:
                        new_avg_p = price
                    elif new_qty > 0:
                        new_avg_p = old_avg_p
                    else:
                        new_avg_p = 0.0
                else:
                    # Adding to Short position
                    new_qty = old_qty - qty
                    new_avg_p = (abs(old_qty) * old_avg_p + qty * price) / abs(new_qty) if abs(new_qty) > 0 else 0.0
                    new_realized = old_realized

            # Create updated position object
            if abs(new_qty) < 1e-8:
                self._positions.pop(symbol, None)
                updated_position = None
            else:
                mkt_price = price
                mkt_val = new_qty * mkt_price
                unrealized = new_qty * (mkt_price - new_avg_p) if new_qty > 0 else abs(new_qty) * (new_avg_p - mkt_price)

                updated_position = PaperPosition(
                    symbol=symbol,
                    quantity=new_qty,
                    average_price=new_avg_p,
                    market_price=mkt_price,
                    market_value=mkt_val,
                    unrealized_pnl=unrealized,
                    realized_pnl=new_realized,
                )
                self._positions[symbol] = updated_position

            account_snapshot = self.get_account_snapshot()
            return account_snapshot, updated_position
