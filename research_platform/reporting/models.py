"""Immutable Pydantic models for Institutional Reporting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class ReportCard(BaseModel):
    """An institutional report summary card."""

    report_id: str
    title: str
    content: str
    format_type: str  # PDF, JSON, MD
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
