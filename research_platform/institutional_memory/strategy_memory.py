"""Strategy Memory mapping strategy parameters state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from research_platform.institutional_memory.models import MemoryMetadata, StrategyMemory


class StrategyMemoryAdapter:
    """Formats strategy configurations to immutable StrategyMemory logs."""

    @staticmethod
    def create_record(
        strategy_id: str,
        version_tag: str,
        sharpe: float,
        sortino: float,
        drawdown: float,
        params: Dict[str, Any],
        parent_ids: List[str] = None
    ) -> StrategyMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-strat-{uuid.uuid4()}",
            version=1,
            originating_subsystem="strategy_lab",
            originating_event="StrategyVersionCreated",
            author="system",
            lineage_parent_ids=parent_ids or []
        )

        return StrategyMemory(
            metadata=meta,
            strategy_id=strategy_id,
            version_tag=version_tag,
            sharpe=sharpe,
            sortino=sortino,
            drawdown=drawdown,
            parameters=params
        )
