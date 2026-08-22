"""Trade Journal — persists rich records for every completed trade."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from research_platform.portfolio_accounting.interfaces import ITradeJournal
from research_platform.portfolio_accounting.models import TradeRecord

logger = logging.getLogger(__name__)


class TradeJournal(ITradeJournal):
    """Immutable in-memory trade ledger with O(1) append and O(n) read.

    In production, this can be wired to a DB repository.
    """

    def __init__(self) -> None:
        self._records: List[TradeRecord] = []
        self._lock = threading.RLock()

    # ── ITradeJournal ────────────────────────────────────────────────────────

    def record(self, trade: TradeRecord) -> None:
        with self._lock:
            self._records.append(trade)
            logger.info(
                "TradeJournal: %s %s qty=%.4f entry=%.4f exit=%.4f pnl=%.2f net=%.2f (%.2f%%)",
                trade.side, trade.symbol,
                trade.quantity, trade.entry_price, trade.exit_price,
                trade.realized_pnl, trade.net_pnl, trade.return_pct,
            )

    def get_all(self) -> List[TradeRecord]:
        with self._lock:
            return list(self._records)

    def get_by_symbol(self, symbol: str) -> List[TradeRecord]:
        with self._lock:
            return [r for r in self._records if r.symbol == symbol]

    # ── Factory helper ────────────────────────────────────────────────────────

    @staticmethod
    def build_record(
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        realized_pnl: float,
        commission: float = 0.0,
        slippage: float = 0.0,
        strategy: str = "",
        ai_confidence: float = 0.0,
        rationale: str = "",
        reason_closed: str = "SIGNAL",
    ) -> TradeRecord:
        exit_time = datetime.now(timezone.utc)
        duration = (exit_time - entry_time).total_seconds()
        net_pnl = realized_pnl - commission - slippage
        cost_basis = entry_price * quantity
        return_pct = (net_pnl / abs(cost_basis)) * 100.0 if cost_basis != 0.0 else 0.0

        return TradeRecord(
            trade_id=f"trd-{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            holding_duration_seconds=duration,
            realized_pnl=realized_pnl,
            return_pct=round(return_pct, 4),
            commission=commission,
            slippage=slippage,
            net_pnl=round(net_pnl, 4),
            strategy=strategy,
            ai_confidence=ai_confidence,
            rationale=rationale,
            reason_closed=reason_closed,
        )
