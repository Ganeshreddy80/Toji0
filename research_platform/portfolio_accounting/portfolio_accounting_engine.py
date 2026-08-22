"""Portfolio Accounting Engine — live cash/equity/exposure ledger."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from research_platform.portfolio_accounting.interfaces import IPortfolioAccountingEngine
from research_platform.portfolio_accounting.models import (
    PortfolioSnapshot,
    ValuatedPosition,
)

logger = logging.getLogger(__name__)


class PortfolioAccountingEngine(IPortfolioAccountingEngine):
    """Maintains a live, consistent portfolio ledger.

    The ledger starts with an initial cash balance and is updated:
      - apply_fill()     — on every confirmed order fill
      - recalculate()    — on every market tick (positions change value)
    """

    def __init__(self, initial_balance: float = 100_000.0) -> None:
        self._initial_balance = initial_balance
        self._cash_balance = initial_balance
        self._reserved_margin = 0.0
        self._realized_pnl = 0.0
        self._fees = 0.0
        self._commission = 0.0
        self._slippage = 0.0
        self._daily_pnl_start: Optional[float] = None
        self._daily_start_time: Optional[datetime] = None
        self._snapshot: Optional[PortfolioSnapshot] = None
        self._lock = threading.RLock()

    # ── IPortfolioAccountingEngine ────────────────────────────────────────────

    def apply_fill(
        self,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        """Adjust cash after a confirmed fill."""
        with self._lock:
            cost = quantity * price
            total_fee = commission + slippage

            if side == "BUY":
                self._cash_balance -= (cost + total_fee)
            else:
                self._cash_balance += (cost - total_fee)

            self._commission += commission
            self._slippage += slippage
            self._fees += total_fee
            logger.debug("PortfolioAccounting: fill applied %s %.4f@%.4f cash=%.2f",
                         side, quantity, price, self._cash_balance)

    def apply_close_pnl(self, realized_pnl: float, commission: float = 0.0) -> None:
        """Record realized PnL from a closed position."""
        with self._lock:
            self._realized_pnl += realized_pnl
            self._commission += commission
            self._fees += commission
            # Cash already adjusted in apply_fill for the closing leg

    def recalculate(self, positions: List[ValuatedPosition]) -> PortfolioSnapshot:
        """Recompute portfolio snapshot from current positions and ledger."""
        with self._lock:
            unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            open_market_value = sum(p.market_value for p in positions)

            portfolio_value = self._cash_balance + open_market_value
            equity = portfolio_value - self._reserved_margin
            buying_power = max(0.0, self._cash_balance)

            # Daily PnL: reset at midnight UTC
            now = datetime.now(timezone.utc)
            if self._daily_start_time is None or self._daily_start_time.date() < now.date():
                self._daily_pnl_start = equity
                self._daily_start_time = now
            daily_pnl = equity - (self._daily_pnl_start or equity)

            self._snapshot = PortfolioSnapshot(
                snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
                cash_balance=round(self._cash_balance, 4),
                reserved_margin=round(self._reserved_margin, 4),
                portfolio_value=round(portfolio_value, 4),
                equity=round(equity, 4),
                buying_power=round(buying_power, 4),
                realized_pnl=round(self._realized_pnl, 4),
                unrealized_pnl=round(unrealized_pnl, 4),
                daily_pnl=round(daily_pnl, 4),
                fees=round(self._fees, 4),
                commission=round(self._commission, 4),
                slippage=round(self._slippage, 4),
                open_position_count=len(positions),
                total_exposure=round(open_market_value, 4),
            )
            return self._snapshot

    def get_snapshot(self) -> Optional[PortfolioSnapshot]:
        with self._lock:
            return self._snapshot

    @property
    def initial_balance(self) -> float:
        return self._initial_balance
