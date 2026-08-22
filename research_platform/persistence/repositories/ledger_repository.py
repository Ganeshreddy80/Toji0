"""PostgreSQL trade ledger repository wrapper.
"""

from __future__ import annotations

from typing import List, Optional
from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import TradeLedgerModel
from research_platform.portfolio_accounting.models import TradeLedgerEntry


class PostgresLedgerRepository(BaseRepository):
    """PostgreSQL-backed Trade Ledger repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, TradeLedgerModel)

    def save_entry(self, entry: TradeLedgerEntry) -> None:
        model = self.get(entry.trade_id)
        if model:
            updates = {
                "order_id": entry.order_id,
                "symbol": entry.symbol,
                "side": entry.side,
                "quantity": entry.quantity,
                "entry_price": entry.entry_price,
                "exit_price": entry.exit_price,
                "commission": entry.commission,
                "slippage": entry.slippage,
                "realized_pnl": entry.realized_pnl,
                "timestamp": entry.timestamp
            }
            self.update(entry.trade_id, updates)
        else:
            new_model = TradeLedgerModel(
                trade_id=entry.trade_id,
                order_id=entry.order_id,
                symbol=entry.symbol,
                side=entry.side,
                quantity=entry.quantity,
                entry_price=entry.entry_price,
                exit_price=entry.exit_price,
                commission=entry.commission,
                slippage=entry.slippage,
                realized_pnl=entry.realized_pnl,
                timestamp=entry.timestamp
            )
            self.create(new_model)

    def get_entry(self, trade_id: str) -> Optional[TradeLedgerEntry]:
        model = self.get(trade_id)
        if model:
            return TradeLedgerEntry(
                trade_id=model.trade_id,
                order_id=model.order_id,
                symbol=model.symbol,
                side=model.side,
                quantity=model.quantity,
                entry_price=model.entry_price,
                exit_price=model.exit_price,
                commission=model.commission,
                slippage=model.slippage,
                realized_pnl=model.realized_pnl,
                timestamp=model.timestamp
            )
        return None

    def list_entries(self) -> List[TradeLedgerEntry]:
        models = self.list_all()
        return [
            TradeLedgerEntry(
                trade_id=m.trade_id,
                order_id=m.order_id,
                symbol=m.symbol,
                side=m.side,
                quantity=m.quantity,
                entry_price=m.entry_price,
                exit_price=m.exit_price,
                commission=m.commission,
                slippage=m.slippage,
                realized_pnl=m.realized_pnl,
                timestamp=m.timestamp
            )
            for m in models
        ]
