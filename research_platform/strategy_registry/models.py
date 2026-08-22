"""Immutable Pydantic models for the Strategy Registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RegisteredStrategy(BaseModel):
    """A strategy entry metadata representation registered in the strategy registry."""

    strategy_id: str
    name: str
    description: str
    active_version: str
    git_hash: str
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    author: str
    asset_class: str
    risk_profile: str  # LOW, MEDIUM, HIGH
    runtime_capabilities: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"  # ACTIVE, DEPRECATED, RETIRED
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class StrategyRegistryStatistics(BaseModel):
    """Statistics card detailing registry entries counts."""

    total_registered: int
    active_count: int
    retired_count: int

    model_config = ConfigDict(frozen=True)


class StrategyRegistrySnapshot(BaseModel):
    """Snapshot card for registry backups."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    strategies: List[RegisteredStrategy] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
