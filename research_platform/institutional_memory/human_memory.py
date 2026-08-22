"""Human Memory mapping governance decisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import HumanMemory, MemoryMetadata


class HumanMemoryAdapter:
    """Formats human reviews to immutable HumanMemory logs."""

    @staticmethod
    def create_record(
        approval_id: str,
        action: str,
        comments: str,
        parent_ids: List[str] = None
    ) -> HumanMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-hum-{uuid.uuid4()}",
            version=1,
            originating_subsystem="governance",
            originating_event="HumanApprovalGranted",
            author="human",
            lineage_parent_ids=parent_ids or []
        )

        return HumanMemory(
            metadata=meta,
            approval_id=approval_id,
            action_approved=action,
            comments=comments,
            decision_timestamp=datetime.now(timezone.utc)
        )
