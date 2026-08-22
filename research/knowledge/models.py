"""Pydantic schemas for documenting knowledge entries and research lessons learned."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """Canonical model for a research Knowledge Entry or Lesson Learned."""

    entry_id: str = Field(...)
    experiment_id: str = Field(..., description="The parent research experiment ID")
    title: str = Field(...)
    concept: str = Field(..., description="The core quantitative or structural finding")
    evidence: str = Field(
        ..., description="Description or statistic citation proving the concept (e.g. t-stat > 2.0)"
    )
    is_lessons_learned: bool = Field(
        default=False,
        description="True if derived from a failed/flawed experiment or risk discovery (warning list)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
