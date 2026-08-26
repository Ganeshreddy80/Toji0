"""R51 Central Configuration Pydantic Models.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """PostgreSQL connection and pooling configurations."""
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = ""
    database: str = "toji"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 5


class ExchangeConfig(BaseModel):
    """Sandbox paper market routing limits."""
    api_key: str = "mock-key"
    api_secret: str = "mock-secret"
    base_url: str = "http://localhost:8080"
    symbol_filters: List[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "GOOG"])
    max_slippage_pct: float = 0.05
    spread_pct: float = 0.01


class StrategyConfig(BaseModel):
    """Strategy registry allocations."""
    strategy_id: str = "default-strat"
    enabled: bool = True
    allocation_pct: float = 1.0
    parameters: Dict[str, Any] = Field(default_factory=dict)


class RiskConfig(BaseModel):
    """Risk guard limit specifications."""
    max_order_size: float = 1000.0
    max_position_size: float = 5000.0
    max_daily_drawdown_pct: float = 0.05
    max_slippage_pct: float = 0.02


class RuntimeConfig(BaseModel):
    """Master loop scheduling timers."""
    interval_sec: float = 1.0
    mode: str = "PAPER"  # DEV, PAPER, PROD
    thread_priority: int = 1


class MonitoringConfig(BaseModel):
    """Telemetry logging metrics thresholds."""
    latency_threshold_ms: float = 50.0
    cpu_limit_pct: float = 80.0
    memory_limit_mb: float = 512.0
    alert_email: str = "admin@toji.local"


class ReportingConfig(BaseModel):
    """Scheduled reports distributions."""
    enabled: bool = True
    frequency_minutes: int = 60
    formats: List[str] = Field(default_factory=lambda: ["MARKDOWN", "JSON"])


class RecoveryConfig(BaseModel):
    """Checkpoints durations and snapshot options."""
    checkpoint_interval_sec: float = 30.0
    max_recovery_retries: int = 3
    backup_snapshots_count: int = 10


class CentralConfig(BaseModel):
    """Platform configuration structure."""
    version: int = 1
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    strategies: List[StrategyConfig] = Field(default_factory=list)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)
