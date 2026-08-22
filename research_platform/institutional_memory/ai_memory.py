"""AI Memory mapping LLM advisor logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import AIMemory, MemoryMetadata


class AIMemoryAdapter:
    """Formats LLM recommendations to immutable AIMemory logs."""

    @staticmethod
    def create_record(
        rec_id: str,
        action: str,
        reasoning: str,
        confidence: float,
        parent_ids: List[str] = None
    ) -> AIMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-ai-{uuid.uuid4()}",
            version=1,
            originating_subsystem="ai_intelligence",
            originating_event="RecommendationGenerated",
            author="AI",
            confidence_score=confidence,
            lineage_parent_ids=parent_ids or []
        )

        return AIMemory(
            metadata=meta,
            recommendation_id=rec_id,
            action=action,
            reasoning=reasoning,
            confidence=confidence
        )
