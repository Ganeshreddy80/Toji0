"""Position Memory mapping position lifecycle data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import MemoryMetadata, PositionMemory


class PositionMemoryAdapter:
    """Formats position statistics to immutable PositionMemory logs."""

    @staticmethod
    def create_record(
        position_id: str,
        symbol: str,
        average_cost: float,
        realized_pnl: float,
        duration: float,
        parent_ids: List[str] = None
    ) -> PositionMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-pos-{uuid.uuid4()}",
            version=1,
            originating_subsystem="portfolio_engine",
            originating_event="PositionClosed",
            author="system",
            lineage_parent_ids=parent_ids or []
        )

        return PositionMemory(
            metadata=meta,
            position_id=position_id,
            symbol=symbol,
            average_cost=average_cost,
            realized_pnl=realized_pnl,
            holding_duration_seconds=duration
        )
