"""PostgreSQL trade journal repository.
"""

from __future__ import annotations

import json
from typing import List, Optional
from sqlalchemy.orm import Session

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import TradeJournalModel, DailyJournalModel, TradeStatisticsModel
from research_platform.trade_journal.models import TradeJournal, DailyJournal, TradeStatistics


class PostgresTradeJournalRepository(BaseRepository):
    """PostgreSQL-backed trade journal repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, TradeJournalModel)
        self._daily_repo = BaseRepository(session_manager, DailyJournalModel)
        self._stats_repo = BaseRepository(session_manager, TradeStatisticsModel)

    def save_journal(self, journal: TradeJournal) -> None:
        serialized = journal.model_dump_json()
        model = self.get(journal.journal_id)
        if model:
            updates = {
                "order_id": journal.order_id,
                "strategy_id": journal.strategy_id,
                "symbol": journal.symbol,
                "pnl": journal.pnl,
                "tags": journal.tags,
                "data": serialized
            }
            self.update(journal.journal_id, updates)
        else:
            new_model = TradeJournalModel(
                journal_id=journal.journal_id,
                order_id=journal.order_id,
                strategy_id=journal.strategy_id,
                symbol=journal.symbol,
                pnl=journal.pnl,
                tags=journal.tags,
                data=serialized
            )
            self.create(new_model)

    def get_journal(self, journal_id: str) -> Optional[TradeJournal]:
        model = self.get(journal_id)
        if model:
            return TradeJournal.model_validate_json(model.data)
        return None

    def list_journals(self) -> List[TradeJournal]:
        models = self.list_all()
        return [TradeJournal.model_validate_json(m.data) for m in models]

    def save_statistics(self, stats: TradeStatistics) -> None:
        serialized = stats.model_dump_json()
        model = self._stats_repo.get("latest")
        if model:
            self._stats_repo.update("latest", {"data": serialized})
        else:
            new_model = TradeStatisticsModel(stats_id="latest", data=serialized)
            self._stats_repo.create(new_model)

    def get_latest_statistics(self) -> Optional[TradeStatistics]:
        model = self._stats_repo.get("latest")
        if model:
            return TradeStatistics.model_validate_json(model.data)
        return None

    def save_daily_journal(self, journal: DailyJournal) -> None:
        serialized = journal.model_dump_json()
        model = self._daily_repo.get(journal.date)
        if model:
            self._daily_repo.update(journal.date, {"data": serialized})
        else:
            new_model = DailyJournalModel(date=journal.date, data=serialized)
            self._daily_repo.create(new_model)

    def get_daily_journal(self, date_str: str) -> Optional[DailyJournal]:
        model = self._daily_repo.get(date_str)
        if model:
            return DailyJournal.model_validate_json(model.data)
        return None


class PostgresTradeRepository(BaseRepository):
    """PostgreSQL-backed trade repository implementation for the 'trades' table."""

    def __init__(self, session_manager) -> None:
        from research_platform.persistence.postgres.migrations import TradeModel
        super().__init__(session_manager, TradeModel)

    def save_trade(self, trade_id: str, order_id: str, symbol: str, side: str, quantity: float, price: float, timestamp: datetime) -> None:
        model = self.get(trade_id)
        if model:
            updates = {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp
            }
            self.update(trade_id, updates)
        else:
            from research_platform.persistence.postgres.migrations import TradeModel
            new_model = TradeModel(
                trade_id=trade_id,
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=timestamp
            )
            self.create(new_model)

    def get_trade(self, trade_id: str) -> Optional[Any]:
        return self.get(trade_id)

    def list_trades(self) -> List[Any]:
        return self.list_all()

