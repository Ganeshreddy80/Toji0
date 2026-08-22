"""Pydantic dashboard models for the Institutional Operations Center.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WidgetState(BaseModel):
    """Generic status indicator for a dashboard widget."""

    widget_name: str
    status: str = "ONLINE"  # ONLINE, DEGRADED, OFFLINE
    last_update: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AlertCard(BaseModel):
    """An alert card capturing severity and messages details."""

    alert_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    priority: str  # INFO, WARNING, CRITICAL
    message: str

    model_config = ConfigDict(frozen=True)


class MetricCard(BaseModel):
    """A generic key-value metric card."""

    key: str
    value: float
    unit: str = ""

    model_config = ConfigDict(frozen=True)


class SystemHealthCard(BaseModel):
    """System health resource parameters snapshot."""

    cpu_usage: float
    ram_usage_mb: float
    thread_count: int
    event_rate_per_sec: float
    log_errors_count: int = 0
    log_warnings_count: int = 0
    status: str = "HEALTHY"

    model_config = ConfigDict(frozen=True)


class PortfolioCard(BaseModel):
    """Sandbox account details card."""

    cash: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    peak_equity: float
    drawdown: float
    leverage: float
    margin_used: float

    model_config = ConfigDict(frozen=True)


class StrategyCard(BaseModel):
    """Active strategy parameter status card."""

    strategy_id: str
    version: str
    lifecycle_stage: str
    status: str  # RUNNING, PAUSED, STOPPED
    market_regime: str
    ai_confidence: float
    risk_status: str
    current_signals: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ExecutionCard(BaseModel):
    """Order routing latency and adapter stats."""

    exchange: str
    rest_status: str
    websocket_status: str
    reconnect_count: int
    retries_count: int
    queue_length: int
    rate_limits: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class MarketCard(BaseModel):
    """Live pricing statistics and feed fresh values."""

    symbol: str
    last_price: float
    spread: float
    volume_24h: float
    feed_latency_ms: float
    feed_fresh: bool

    model_config = ConfigDict(frozen=True)


class RiskCard(BaseModel):
    """Exposures and CVaR boundaries metrics."""

    current_exposure: float
    var_99: float
    cvar_99: float
    kill_switch_active: bool
    open_violations: int

    model_config = ConfigDict(frozen=True)


class AICard(BaseModel):
    """AI recommendations and analysis outputs."""

    recommendation: str
    rationale: str
    confidence: float
    reasoning: str
    current_research: str

    model_config = ConfigDict(frozen=True)


class MemoryCard(BaseModel):
    """Recent memory logs registers."""

    recent_keys: List[str] = Field(default_factory=list)
    active_categories: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class SimulationCard(BaseModel):
    """Replay validations health statistics."""

    latest_replay_id: str
    replication_error: float
    stress_result: str
    status: str

    model_config = ConfigDict(frozen=True)


class DashboardSnapshot(BaseModel):
    """Unified operations dashboard snapshot wrapping all widgets."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    health: SystemHealthCard
    portfolio: PortfolioCard
    strategies: List[StrategyCard] = Field(default_factory=list)
    executions: List[ExecutionCard] = Field(default_factory=list)
    markets: List[MarketCard] = Field(default_factory=list)
    risk: RiskCard
    ai: AICard
    memory: MemoryCard
    simulation: SimulationCard
    alerts: List[AlertCard] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
