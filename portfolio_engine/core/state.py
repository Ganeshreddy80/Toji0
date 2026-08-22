from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from portfolio_engine.core.enums import PositionSide, PositionState
from portfolio_engine.core.models import (
    Position,
    ClosedPosition,
    PortfolioSnapshot,
    PortfolioMetrics,
    PortfolioHealth,
    PortfolioStatistics,
)
from portfolio_engine.storage.position_store import PositionStore
from portfolio_engine.storage.history_store import HistoryStore
from portfolio_engine.analysis.pnl_calculator import PnlCalculator
from portfolio_engine.analysis.exposure import ExposureCalculator
from portfolio_engine.analysis.portfolio_metrics import PortfolioMetricsCalculator
from portfolio_engine.analysis.portfolio_health import PortfolioHealthCalculator


class PortfolioStateStore:
    """Thread-safe state manager aggregating active positions, history, and metrics."""

    def __init__(self, initial_balance: float = 100000.0) -> None:
        self._lock = threading.Lock()
        self._initial_balance = initial_balance
        self._peak_value = initial_balance
        
        self._position_store = PositionStore()
        self._history_store = HistoryStore()
        
        # Initialize default snapshot
        self._current_snapshot = self._rebuild_snapshot_unlocked()

    def get_current_snapshot(self) -> PortfolioSnapshot:
        """Fetch the latest portfolio snapshot."""
        with self._lock:
            return self._current_snapshot

    def get_history(self) -> List[PortfolioSnapshot]:
        """Fetch historical snapshots."""
        return self._history_store.get_history()

    def clear(self) -> None:
        """Reset all states."""
        with self._lock:
            self._position_store.clear()
            self._history_store.clear()
            self._peak_value = self._initial_balance
            self._current_snapshot = self._rebuild_snapshot_unlocked()

    def update_market_price(self, symbol: str, current_price: float) -> PortfolioSnapshot:
        """Update last known market price for a symbol and recalculate PnL/metrics."""
        with self._lock:
            pos = self._position_store.get_position(symbol)
            if pos:
                unrealized = PnlCalculator.calculate_unrealized_pnl(
                    pos.side, pos.quantity, pos.average_entry, current_price
                )
                mval = pos.quantity * current_price
                margin = mval / pos.leverage
                
                updated_pos = pos.model_copy(
                    update={
                        "current_price": current_price,
                        "market_value": mval,
                        "unrealized_pnl": unrealized,
                        "margin_used": margin,
                        "exposure": mval,
                    }
                )
                self._position_store.save_position(updated_pos)
                
            self._current_snapshot = self._rebuild_snapshot_unlocked()
            self._history_store.add_snapshot(self._current_snapshot)
            return self._current_snapshot

    def apply_position_fill(
        self,
        position_id: str,
        symbol: str,
        side: PositionSide,
        quantity: float,
        price: float,
        leverage: float = 1.0,
        margin_required: float = 0.0,
        fees: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> tuple[PortfolioSnapshot, Optional[Position], Optional[ClosedPosition]]:
        """Process a fill, modify or close active positions, and return updates."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        with self._lock:
            pos = self._position_store.get_position(symbol)
            opened_pos: Optional[Position] = None
            closed_pos: Optional[ClosedPosition] = None

            from portfolio_engine.core.models import PositionUpdate

            update_entry = PositionUpdate(
                timestamp=timestamp,
                price=price,
                quantity=quantity,
                pnl=0.0,
                action="ENTRY" if not pos else "ADD",
            )

            if not pos:
                # 1. Open new position
                mval = quantity * price
                margin = margin_required if margin_required > 0.0 else (mval / leverage)
                
                pos = Position(
                    position_id=position_id,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    average_entry=price,
                    current_price=price,
                    market_value=mval,
                    cost_basis=mval,
                    exposure=mval,
                    leverage=leverage,
                    margin_used=margin,
                    fees=fees,
                    open_time=timestamp,
                    state=PositionState.OPEN,
                    updates=[update_entry],
                )
                self._position_store.save_position(pos)
                opened_pos = pos
            else:
                # 2. Modify existing position
                # Check if adding or reducing
                is_add = (pos.side == PositionSide.LONG and side == PositionSide.LONG) or \
                         (pos.side == PositionSide.SHORT and side == PositionSide.SHORT)

                if is_add:
                    # Add to position size
                    new_qty = pos.quantity + quantity
                    new_entry = PnlCalculator.calculate_weighted_average_entry(
                        pos.quantity, pos.average_entry, quantity, price
                    )
                    mval = new_qty * price
                    margin = pos.margin_used + (margin_required if margin_required > 0.0 else (quantity * price / leverage))
                    
                    pos = pos.model_copy(
                        update={
                            "quantity": new_qty,
                            "average_entry": new_entry,
                            "current_price": price,
                            "market_value": mval,
                            "cost_basis": pos.cost_basis + (quantity * price),
                            "exposure": mval,
                            "margin_used": margin,
                            "fees": pos.fees + fees,
                            "updates": pos.updates + [update_entry],
                        }
                    )
                    self._position_store.save_position(pos)
                else:
                    # Reduce or close position
                    if quantity >= pos.quantity:
                        # Complete close
                        realized = PnlCalculator.calculate_realized_pnl(
                            pos.side, pos.average_entry, price, pos.quantity, fees
                        )
                        
                        update_close = PositionUpdate(
                            timestamp=timestamp,
                            price=price,
                            quantity=pos.quantity,
                            pnl=realized,
                            action="CLOSE",
                        )

                        closed_pos = ClosedPosition(
                            position_id=pos.position_id,
                            symbol=pos.symbol,
                            side=pos.side,
                            quantity=pos.quantity,
                            average_entry=pos.average_entry,
                            average_exit=price,
                            realized_pnl=pos.realized_pnl + realized,
                            fees=pos.fees + fees,
                            funding=pos.funding,
                            open_time=pos.open_time,
                            close_time=timestamp,
                            updates=pos.updates + [update_close],
                        )
                        self._position_store.add_closed_position(closed_pos)
                        self._position_store.remove_position(symbol)
                        pos = None
                    else:
                        # Partial reduction
                        realized = PnlCalculator.calculate_realized_pnl(
                            pos.side, pos.average_entry, price, quantity, fees
                        )
                        new_qty = pos.quantity - quantity
                        mval = new_qty * price
                        margin = pos.margin_used * (new_qty / pos.quantity)
                        
                        update_reduce = PositionUpdate(
                            timestamp=timestamp,
                            price=price,
                            quantity=quantity,
                            pnl=realized,
                            action="REDUCE",
                        )

                        pos = pos.model_copy(
                            update={
                                "quantity": new_qty,
                                "current_price": price,
                                "market_value": mval,
                                "exposure": mval,
                                "margin_used": margin,
                                "realized_pnl": pos.realized_pnl + realized,
                                "fees": pos.fees + fees,
                                "updates": pos.updates + [update_reduce],
                            }
                        )
                        self._position_store.save_position(pos)

            self._current_snapshot = self._rebuild_snapshot_unlocked()
            self._history_store.add_snapshot(self._current_snapshot)
            return self._current_snapshot, opened_pos, closed_pos

    def _rebuild_snapshot_unlocked(self) -> PortfolioSnapshot:
        """Rebuild snapshot stats based on current registrations."""
        positions = self._position_store.get_all_positions()
        closed = self._position_store.get_closed_positions()
        
        # 1. PnL calculations
        total_realized = sum(p.realized_pnl for p in closed)
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        margin = sum(p.margin_used for p in positions)

        portfolio_value = self._initial_balance + total_realized + total_unrealized
        self._peak_value = max(self._peak_value, portfolio_value)

        # 2. Exposure calculations
        gross, net = ExposureCalculator.calculate_exposures(positions)

        # 3. Compile metrics and health
        metrics = PortfolioMetrics(
            total_realized_pnl=total_realized,
            total_unrealized_pnl=total_unrealized,
            gross_exposure=gross,
            net_exposure=net,
            portfolio_value=portfolio_value,
            margin_used=margin,
            leverage_ratio=gross / portfolio_value if portfolio_value > 0.0 else 0.0,
        )

        health = PortfolioHealthCalculator.calculate_health(
            portfolio_value=portfolio_value,
            peak_value=self._peak_value,
            gross_exposure=gross,
            margin_used=margin,
        )

        return PortfolioSnapshot(
            snapshot_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            positions={p.symbol.upper(): p for p in positions},
            closed_positions=closed,
            metrics=metrics,
            health=health,
        )

    def get_statistics(self) -> PortfolioStatistics:
        """Compute live trade statistics across closed positions."""
        closed = self._position_store.get_closed_positions()
        return PortfolioMetricsCalculator.calculate_statistics(closed)
