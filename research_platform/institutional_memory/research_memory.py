"""Research Memory mapping experiments backtesting.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import MemoryMetadata, ResearchMemory


class ResearchMemoryAdapter:
    """Formats experiment outputs to immutable ResearchMemory logs."""

    @staticmethod
    def create_record(
        hypothesis_id: str,
        experiment_name: str,
        sharpe: float,
        drawdown: float,
        validated: bool,
        parent_ids: List[str] = None
    ) -> ResearchMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-res-{uuid.uuid4()}",
            version=1,
            originating_subsystem="research_data_platform",
            originating_event="ExperimentCompleted",
            author="system",
            lineage_parent_ids=parent_ids or []
        )

        return ResearchMemory(
            metadata=meta,
            hypothesis_id=hypothesis_id,
            experiment_name=experiment_name,
            sharpe=sharpe,
            drawdown=drawdown,
            validated=validated
        )
