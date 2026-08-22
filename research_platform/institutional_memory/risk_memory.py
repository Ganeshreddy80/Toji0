"""Risk Memory mapping VaR limit limits parameters.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import MemoryMetadata, RiskMemory


class RiskMemoryAdapter:
    """Formats risk thresholds to immutable RiskMemory logs."""

    @staticmethod
    def create_record(
        var_limit: float,
        cvar_limit: float,
        leverage_limit: float,
        breaches_count: int,
        kill_switch: bool,
        parent_ids: List[str] = None
    ) -> RiskMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-risk-{uuid.uuid4()}",
            version=1,
            originating_subsystem="risk_management",
            originating_event="RiskAssessmentCompleted",
            author="system",
            lineage_parent_ids=parent_ids or []
        )

        return RiskMemory(
            metadata=meta,
            var_limit=var_limit,
            cvar_limit=cvar_limit,
            leverage_limit=leverage_limit,
            active_breaches_count=breaches_count,
            kill_switch_active=kill_switch
        )
