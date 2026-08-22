"""PostgreSQL position repository wrapper.
"""

from __future__ import annotations

from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import PositionModel
from research_platform.paper_trading.models import PaperPosition


class PostgresPositionRepository(BaseRepository):
    """PostgreSQL-backed Position repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, PositionModel)

    def save_position(self, position: PaperPosition) -> None:
        model = self.get(position.symbol)
        if model:
            updates = {
                "quantity": position.quantity,
                "average_price": position.entry_price
            }
            self.update(position.symbol, updates)
        else:
            new_model = PositionModel(
                position_id=position.symbol,
                symbol=position.symbol,
                quantity=position.quantity,
                average_price=position.entry_price
            )
            self.create(new_model)

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        model = self.get(symbol)
        if model:
            return PaperPosition(
                symbol=model.symbol,
                quantity=model.quantity,
                entry_price=model.average_price,
                current_price=model.average_price
            )
        return None

    def list_positions(self) -> List[PaperPosition]:
        models = self.list_all()
        return [
            PaperPosition(
                symbol=m.symbol,
                quantity=m.quantity,
                entry_price=m.average_price,
                current_price=m.average_price
            )
            for m in models
        ]

