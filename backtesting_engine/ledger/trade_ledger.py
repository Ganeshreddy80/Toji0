"""Trade ledger tracking position history, entry/exit prices, and PnL accounting (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional

from backtesting_engine.core.enums import PositionSide, TradeStatus
from backtesting_engine.core.events import TradeClosed, TradeOpened
from backtesting_engine.core.exceptions import TradeLedgerError
from backtesting_engine.core.interfaces import ITradeLedger
from backtesting_engine.core.models import MarketBar, SimulatedFill, TradeRecord
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class TradeLedger(ITradeLedger):
    """Thread-safe trade history ledger tracking open/closed positions and realized/unrealized PnL."""

    def __init__(self, event_bus: Optional[IEventBus] = None) -> None:
        self._open_trades: Dict[str, TradeRecord] = {}  # symbol -> TradeRecord
        self._closed_trades: List[TradeRecord] = []
        self._lock = threading.RLock()
        self._event_bus = event_bus

    def process_fill(self, fill: SimulatedFill, current_bar: MarketBar) -> TradeRecord:
        """Process a fill, updating existing open position or creating a new trade record."""
        if not fill or fill.fill_quantity <= 0.0 or fill.fill_price <= 0.0:
            raise TradeLedgerError("Invalid fill provided for ledger processing.")

        with self._lock:
            existing = self._open_trades.get(fill.symbol)

            if not existing:
                # Open a new trade position
                trade = TradeRecord(
                    order_id=fill.order_id,
                    symbol=fill.symbol,
                    side=fill.side,
                    entry_price=fill.fill_price,
                    quantity=fill.fill_quantity,
                    commission=fill.fee,
                    status=TradeStatus.OPEN,
                    opened_at=fill.timestamp,
                )
                self._open_trades[fill.symbol] = trade

                if self._event_bus:
                    self._event_bus.publish(
                        TradeOpened(
                            source="backtesting.ledger",
                            payload={
                                "trade_id": trade.trade_id,
                                "symbol": trade.symbol,
                                "side": trade.side.value,
                                "entry_price": trade.entry_price,
                                "quantity": trade.quantity,
                            },
                        )
                    )
                logger.info("TradeLedger: Opened trade %s on %s (%s @ %f)", trade.trade_id, trade.symbol, trade.side.value, trade.entry_price)
                return trade

            elif existing.side == fill.side:
                # Scale up existing position (calculate weighted entry price)
                tot_qty = existing.quantity + fill.fill_quantity
                weighted_entry = ((existing.entry_price * existing.quantity) + (fill.fill_price * fill.fill_quantity)) / tot_qty
                tot_comm = existing.commission + fill.fee

                updated = existing.model_copy(
                    update={
                        "entry_price": round(weighted_entry, 6),
                        "quantity": round(tot_qty, 6),
                        "commission": round(tot_comm, 4),
                    }
                )
                self._open_trades[fill.symbol] = updated
                return updated

            else:
                # Opposite side fill: Close existing position
                exit_price = fill.fill_price
                qty = min(existing.quantity, fill.fill_quantity)

                if existing.side == PositionSide.LONG:
                    gross_pnl = (exit_price - existing.entry_price) * qty
                else:  # SHORT
                    gross_pnl = (existing.entry_price - exit_price) * qty

                tot_comm = existing.commission + fill.fee
                realized_pnl = round(gross_pnl - tot_comm, 4)

                closed_trade = existing.model_copy(
                    update={
                        "exit_price": exit_price,
                        "quantity": qty,
                        "commission": tot_comm,
                        "realized_pnl": realized_pnl,
                        "unrealized_pnl": 0.0,
                        "status": TradeStatus.CLOSED,
                        "closed_at": fill.timestamp,
                    }
                )

                self._open_trades.pop(fill.symbol)
                self._closed_trades.append(closed_trade)

                if self._event_bus:
                    self._event_bus.publish(
                        TradeClosed(
                            source="backtesting.ledger",
                            payload={
                                "trade_id": closed_trade.trade_id,
                                "symbol": closed_trade.symbol,
                                "side": closed_trade.side.value,
                                "exit_price": exit_price,
                                "realized_pnl": realized_pnl,
                            },
                        )
                    )

                logger.info("TradeLedger: Closed trade %s on %s (PnL: %f)", closed_trade.trade_id, closed_trade.symbol, realized_pnl)
                return closed_trade

    def update_unrealized_pnl(self, current_bar: MarketBar) -> float:
        """Update mark-to-market unrealized PnL for open positions against current bar."""
        if not current_bar or current_bar.close <= 0.0:
            return 0.0

        with self._lock:
            existing = self._open_trades.get(current_bar.symbol)
            if not existing:
                return 0.0

            close = current_bar.close
            if existing.side == PositionSide.LONG:
                unrealized = (close - existing.entry_price) * existing.quantity
            else:  # SHORT
                unrealized = (existing.entry_price - close) * existing.quantity

            unrealized = round(unrealized, 4)
            updated = existing.model_copy(update={"unrealized_pnl": unrealized})
            self._open_trades[current_bar.symbol] = updated
            return unrealized

    def get_open_trades(self) -> List[TradeRecord]:
        """Retrieve all currently open trade positions."""
        with self._lock:
            return list(self._open_trades.values())

    def get_closed_trades(self) -> List[TradeRecord]:
        """Retrieve all closed trade records."""
        with self._lock:
            return list(self._closed_trades)
