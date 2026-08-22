"""Trade Memory mapping execution outcomes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import MemoryMetadata, TradeMemory


class TradeMemoryAdapter:
    """Formats execution details to immutable TradeMemory logs."""

    @staticmethod
    def create_record(
        trade_id: str,
        symbol: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        slippage_ms: float,
        quality: str,
        parent_ids: List[str] = None
    ) -> TradeMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-tr-{uuid.uuid4()}",
            version=1,
            originating_subsystem="execution_engine",
            originating_event="TradeCompleted",
            author="system",
            lineage_parent_ids=parent_ids or []
        )

        return TradeMemory(
            metadata=meta,
            trade_id=trade_id,
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            slippage_ms=slippage_ms,
            execution_quality=quality
        )
