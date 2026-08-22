"""Immutable Pydantic models for the Configuration Manager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class ConfigurationEntry(BaseModel):
    """A versioned configuration record containing parameters parameters."""

    config_id: str
    scope: str  # GLOBAL, STRATEGY, RISK, EXCHANGE
    params: Dict[str, Any] = Field(default_factory=dict)
    version: int
    is_active: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ConfigurationSnapshot(BaseModel):
    """A snapshot of all active runtime configurations."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entries: List[ConfigurationEntry] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
