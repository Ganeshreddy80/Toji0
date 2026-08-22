"""Backtesting strategy runner, order simulation, and portfolio state tracker."""

from __future__ import annotations

import uuid
from datetime import datetime
import numpy as np
import pandas as pd

from analytics.backtesting.costs import ICommissionModel, ISlippageModel, ZeroCommissionModel, ZeroSlippageModel
from analytics.backtesting.models import Order, Trade, Position, PortfolioState


class StrategyRunner:
    """Simulates portfolio operations, ledger bookkeeping, and order matching."""

    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission_model: ICommissionModel | None = None,
        slippage_model: ISlippageModel | None = None,
    ) -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_model = commission_model or ZeroCommissionModel()
        self.slippage_model = slippage_model or ZeroSlippageModel()
        
        # State tracking
        self.positions: dict[str, Position] = {}
        self.ledger: list[Trade] = []
        self.equity_history: list[PortfolioState] = []
        
        # Callbacks (Hooks)
        self.on_order_submitted: list[callable] = []
        self.on_trade_executed: list[callable] = []

    def submit_order(
        self,
        order: Order,
        current_price: float,
        volatility: float = 0.0,
    ) -> Trade | None:
        """Process and simulate execution of an order."""
        for hook in self.on_order_submitted:
            hook(order)
            
        symbol = order.symbol
        qty = order.qty
        side = order.side
        timestamp = order.timestamp
        
        existing = self.positions.get(symbol)
        
        # Calculate cost adjustments
        if side == "buy":
            slippage = self.slippage_model.calculate_slippage(current_price, qty, "buy", volatility)
            fill_price = current_price + slippage
            commission = self.commission_model.calculate_commission(qty, fill_price)
            
            # Cash flow: buy costs cash
            self.cash -= (qty * fill_price + commission)
            
            realized_pnl = 0.0
            
            if existing is None:
                # New long position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    qty=qty,
                    avg_entry_price=fill_price,
                    realized_pnl=0.0
                )
            else:
                if existing.qty >= 0.0:
                    # Increase long position
                    new_qty = existing.qty + qty
                    new_avg = (existing.qty * existing.avg_entry_price + qty * fill_price) / new_qty
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        qty=new_qty,
                        avg_entry_price=new_avg,
                        realized_pnl=existing.realized_pnl
                    )
                else:
                    # Reduce or flip short position
                    closed_qty = min(abs(existing.qty), qty)
                    realized_pnl = (existing.avg_entry_price - fill_price) * closed_qty
                    
                    new_qty = existing.qty + qty # e.g. -5 + 2 = -3, or -2 + 5 = 3
                    
                    if new_qty == 0.0:
                        self.positions.pop(symbol, None)
                    elif new_qty < 0.0:
                        self.positions[symbol] = Position(
                            symbol=symbol,
                            qty=new_qty,
                            avg_entry_price=existing.avg_entry_price,
                            realized_pnl=existing.realized_pnl + realized_pnl
                        )
                    else:
                        # Flipping to long
                        self.positions[symbol] = Position(
                            symbol=symbol,
                            qty=new_qty,
                            avg_entry_price=fill_price,
                            realized_pnl=existing.realized_pnl + realized_pnl
                        )
        else:  # sell
            slippage = self.slippage_model.calculate_slippage(current_price, qty, "sell", volatility)
            fill_price = current_price - slippage
            commission = self.commission_model.calculate_commission(qty, fill_price)
            
            # Cash flow: sell adds cash
            self.cash += (qty * fill_price - commission)
            
            realized_pnl = 0.0
            
            if existing is None:
                # New short position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    qty=-qty,
                    avg_entry_price=fill_price,
                    realized_pnl=0.0
                )
            else:
                if existing.qty <= 0.0:
                    # Increase short position
                    new_qty = existing.qty - qty
                    new_avg = (abs(existing.qty) * existing.avg_entry_price + qty * fill_price) / abs(new_qty)
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        qty=new_qty,
                        avg_entry_price=new_avg,
                        realized_pnl=existing.realized_pnl
                    )
                else:
                    # Reduce or flip long position
                    closed_qty = min(existing.qty, qty)
                    realized_pnl = (fill_price - existing.avg_entry_price) * closed_qty
                    
                    new_qty = existing.qty - qty # e.g. 5 - 2 = 3, or 2 - 5 = -3
                    
                    if new_qty == 0.0:
                        self.positions.pop(symbol, None)
                    elif new_qty > 0.0:
                        self.positions[symbol] = Position(
                            symbol=symbol,
                            qty=new_qty,
                            avg_entry_price=existing.avg_entry_price,
                            realized_pnl=existing.realized_pnl + realized_pnl
                        )
                    else:
                        # Flipping to short
                        self.positions[symbol] = Position(
                            symbol=symbol,
                            qty=new_qty,
                            avg_entry_price=fill_price,
                            realized_pnl=existing.realized_pnl + realized_pnl
                        )
                        
        trade = Trade(
            trade_id=str(uuid.uuid4()),
            symbol=symbol,
            qty=qty,
            price=fill_price,
            side=side,
            timestamp=timestamp,
            commission=commission,
            slippage=slippage,
            realized_pnl=realized_pnl
        )
        self.ledger.append(trade)
        
        for hook in self.on_trade_executed:
            hook(trade)
            
        return trade

    def update_valuations(self, timestamp: datetime, prices: dict[str, float]) -> PortfolioState:
        """Update active positions and record snapshot of overall portfolio equity."""
        holdings_value = 0.0
        
        for symbol, pos in self.positions.items():
            curr_price = prices.get(symbol, pos.avg_entry_price)
            if pos.qty > 0.0:
                # Long valuation
                holdings_value += pos.qty * curr_price
            else:
                # Short valuation (cash-settled net asset value)
                # Short value = -qty * (avg_entry_price - curr_price) + -qty * avg_entry_price
                # Which simplifies to: Short Value = -qty * (2 * avg_entry_price - curr_price) or more simply:
                # Cost to cover = abs(qty) * curr_price. Net cash balance covers it.
                # So value of short position is: qty * curr_price (negative value)
                # Cash contains short sales proceeds, holdings contains short position liability.
                # Total Equity = Cash + Holdings = Cash + qty * curr_price (qty is negative)
                holdings_value += pos.qty * curr_price
                
        total_equity = self.cash + holdings_value
        
        state = PortfolioState(
            timestamp=timestamp,
            cash=self.cash,
            holdings_value=holdings_value,
            total_equity=total_equity
        )
        self.equity_history.append(state)
        return state

    def get_equity_curve(self) -> pd.Series:
        """Retrieve the historical equity curve as a pandas Series."""
        if not self.equity_history:
            return pd.Series(dtype=float)
        dates = [s.timestamp for s in self.equity_history]
        vals = [s.total_equity for s in self.equity_history]
        return pd.Series(vals, index=dates)

    def get_returns(self) -> pd.Series:
        """Retrieve the percentage returns series calculated from the equity curve."""
        eq = self.get_equity_curve()
        if eq.empty:
            return pd.Series(dtype=float)
        return eq.pct_change().dropna()
