"""Immutable Pydantic models for the Strategy Lifecycle Manager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StrategyVersion(BaseModel):
    """Execution code version of a strategy."""

    strategy_id: str
    version_id: str
    git_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class StrategyMetadata(BaseModel):
    """Metadata detailing strategy properties."""

    name: str
    description: str
    author: str
    asset_class: str

    model_config = ConfigDict(frozen=True)


class StrategyApproval(BaseModel):
    """Gate approval status logs."""

    gate_name: str  # RISK, PERFORMANCE, COMMITTEE, AI
    approved: bool
    reviewer: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str

    model_config = ConfigDict(frozen=True)


class StrategyPromotion(BaseModel):
    """Promotion logs."""

    strategy_id: str
    version_id: str
    from_status: str
    to_status: str
    promoted_by: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class StrategyRollback(BaseModel):
    """Rollback execution details."""

    strategy_id: str
    from_version: str
    to_version: str
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class StrategyAudit(BaseModel):
    """Transition state change audit card."""

    action: str
    strategy_id: str
    previous_state: str
    new_state: str
    actor: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str

    model_config = ConfigDict(frozen=True)


class StrategyHealth(BaseModel):
    """Active diagnostic checks card."""

    strategy_id: str
    status: str  # HEALTHY, DEGRADED, CRITICAL
    last_checked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_count: int

    model_config = ConfigDict(frozen=True)


class StrategyDeployment(BaseModel):
    """Deployment configurations card."""

    deployment_id: str
    strategy_id: str
    environment: str  # PAPER, STAGING, PRODUCTION
    deployed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class StrategyStatistics(BaseModel):
    """Attribution metrics from simulated paper trading executions."""

    win_rate: float
    pnl: float
    sharpe_ratio: float
    max_drawdown: float
    trades_count: int
    paper_duration_days: float

    model_config = ConfigDict(frozen=True)


class StrategyStatus(BaseModel):
    """Current state details for a strategy."""

    strategy_id: str
    status: str  # DRAFT, RESEARCH, BACKTEST, OPTIMIZATION, WALKFORWARD, PAPER, CANDIDATE, APPROVED, PRODUCTION, PAUSED, RETIRED
    version_id: str
    metadata: StrategyMetadata
    statistics: StrategyStatistics
    health: StrategyHealth

    model_config = ConfigDict(frozen=True)


class LifecycleHistory(BaseModel):
    """Logs lifecycle changes."""

    strategy_id: str
    changes: List[StrategyAudit] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PromotionHistory(BaseModel):
    """Logs promotion events."""

    strategy_id: str
    promotions: List[StrategyPromotion] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ApprovalHistory(BaseModel):
    """Logs approvals gates."""

    strategy_id: str
    gates: List[StrategyApproval] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class DeploymentHistory(BaseModel):
    """Logs deployments."""

    strategy_id: str
    deployments: List[StrategyDeployment] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class LifecycleSnapshot(BaseModel):
    """Full lifecycle tracking state summary snapshot."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status_counts: Dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
