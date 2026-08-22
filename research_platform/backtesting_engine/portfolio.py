"""Portfolio Engine tracking position holdings, realized and unrealized PnL.
"""

from __future__ import annotations

from typing import Dict

from research_platform.backtesting_engine.interfaces import IPortfolioTracker
from research_platform.backtesting_engine.models import MarketEvent, OrderFill, Position, PortfolioState


class PortfolioTracker(IPortfolioTracker):
    """Monitors capital updates, position entry metrics, realized profits, and margin limits."""

    def __init__(self, initial_capital: float, margin_requirement_pct: float = 0.5) -> None:
        self._cash = initial_capital
        self._initial_capital = initial_capital
        self._margin_requirement_pct = margin_requirement_pct
        self._positions: Dict[str, Position] = {}
        self._realized_pnl = 0.0

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> Dict[str, Position]:
        return self._positions

    def process_fill(self, fill: OrderFill) -> PortfolioState:
        """Update cash, realized PnL, margin requirements, and position lists based on transaction fills."""
        symbol = fill.symbol
        qty = fill.quantity
        price = fill.price
        comm = fill.commission

        # Find if direction is buy or sell (requires tracking order context or determining net unit shifts)
        # We assume direction details can be derived or passed. To keep it simple, we check net positions.
        # We can look up existing position. If none, we open long or short.
        # Let's see: we can look up order direction or infer: positive units are BUY, negative are SELL.
        # For simplicity, if we buy -> positive qty. If we sell -> negative qty.
        # Let's verify direction: let's determine direction. If we buy, qty is positive.
        
        # Adjust cash for trade cost + commission
        trade_cost = qty * price
        
        # Deduct trade cost and commissions from cash
        self._cash -= comm

        if symbol not in self._positions:
            # Open new position
            margin_req = abs(qty) * price * self._margin_requirement_pct
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=qty,
                avg_entry_price=price,
                current_price=price,
                unrealized_pnl=0.0,
                margin_requirement=margin_req
            )
        else:
            pos = self._positions[symbol]
            new_qty = pos.quantity + qty
            
            if new_qty == 0.0:
                # Position closed
                realized = pos.quantity * (price - pos.avg_entry_price)
                self._realized_pnl += realized
                self._cash += pos.quantity * price
                del self._positions[symbol]
            else:
                # Position adjusted
                if (pos.quantity > 0 and qty > 0) or (pos.quantity < 0 and qty < 0):
                    # Average up/down
                    new_avg = (pos.quantity * pos.avg_entry_price + qty * price) / new_qty
                    margin_req = abs(new_qty) * price * self._margin_requirement_pct
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        quantity=new_qty,
                        avg_entry_price=new_avg,
                        current_price=price,
                        unrealized_pnl=0.0,
                        margin_requirement=margin_req
                    )
                else:
                    # Partial close
                    realized = abs(qty) * (price - pos.avg_entry_price) * (1.0 if pos.quantity > 0 else -1.0)
                    self._realized_pnl += realized
                    self._cash += abs(qty) * price * (1.0 if pos.quantity > 0 else -1.0)
                    margin_req = abs(new_qty) * price * self._margin_requirement_pct
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        quantity=new_qty,
                        avg_entry_price=pos.avg_entry_price,
                        current_price=price,
                        unrealized_pnl=0.0,
                        margin_requirement=margin_req
                    )

        return self._build_state(fill.timestamp)

    def mark_to_market(self, market_data: MarketEvent) -> PortfolioState:
        """Recalculate unrealized PnL and total equity curves."""
        symbol = market_data.symbol
        close_price = market_data.data.get("close", 0.0)

        if symbol in self._positions:
            pos = self._positions[symbol]
            # Unrealized = units * (current - entry) for longs, units * (entry - current) for shorts
            unrealized = pos.quantity * (close_price - pos.avg_entry_price)
            margin_req = abs(pos.quantity) * close_price * self._margin_requirement_pct
            
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=pos.quantity,
                avg_entry_price=pos.avg_entry_price,
                current_price=close_price,
                unrealized_pnl=unrealized,
                margin_requirement=margin_req
            )

        return self._build_state(market_data.timestamp)

    def _build_state(self, timestamp: datetime) -> PortfolioState:
        """Construct current PortfolioState model."""
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        margin = sum(p.margin_requirement for p in self._positions.values())
        
        # Equity = Cash + Position Value (which is Cash + Unrealized PnL if cash is adjusted during close)
        # In our implementation: cash is adjusted on fill. So cash tracks realized balance.
        # Position value adds unrealized PnL. So Equity = Cash + Unrealized PnL.
        equity = self._cash + unrealized
        buying_power = max(equity - margin, 0.0)

        return PortfolioState(
            timestamp=timestamp,
            cash=self._cash,
            equity=equity,
            margin=margin,
            buying_power=buying_power,
            positions=self._positions.copy(),
            realized_pnl=self._realized_pnl,
            unrealized_pnl=unrealized
        )
