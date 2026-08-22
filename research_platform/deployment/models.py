"""Immutable Pydantic models for the Deployment Manager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StrategyDeployment(BaseModel):
    """An active strategy deployment entry."""

    deployment_id: str
    strategy_id: str
    environment: str  # PAPER, STAGING, PRODUCTION
    status: str  # IN_PROGRESS, ACTIVE, FAILED, ROLLED_BACK
    version_id: str
    active_weight: float = 100.0  # Used in canary weights allocations
    deployed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class DeploymentLock(BaseModel):
    """Global deployment lock preventing concurrent rollouts."""

    is_locked: bool
    locked_by: Optional[str] = None
    reason: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class DeploymentHealthCard(BaseModel):
    """Runtime health indicators for deployed modules."""

    deployment_id: str
    error_count: int
    latency_ms: float
    status: str = "HEALTHY"  # HEALTHY, DEGRADED, CRITICAL

    model_config = ConfigDict(frozen=True)


class DeploymentSnapshot(BaseModel):
    """A backup snapshot of active deployment states."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployments: List[StrategyDeployment] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
