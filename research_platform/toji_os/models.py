"""Immutable Pydantic models for TOJI Operating System.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class OSSession(BaseModel):
    """An active OS control session."""

    session_id: str
    user_id: str
    active: bool = True
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class WorkspaceState(BaseModel):
    """Active workspace parameters configurations."""

    workspace_root: str
    corpus_name: str
    active_strategies: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
