"""Risk Governance models — kill switch states, risk assessments, and anomaly records."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class KillSwitchState(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    REDUCED_RISK = "REDUCED_RISK"
    HALTED = "HALTED"


class TriggerReason(str, Enum):
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    ABNORMAL_VOLATILITY = "ABNORMAL_VOLATILITY"
    EXCHANGE_DISCONNECT = "EXCHANGE_DISCONNECT"
    EXECUTION_QUALITY_DROP = "EXECUTION_QUALITY_DROP"
    FLASH_CRASH = "FLASH_CRASH"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    SPREAD_EXPLOSION = "SPREAD_EXPLOSION"
    MANIPULATION_WICK = "MANIPULATION_WICK"
    LIQUIDITY_VANISH = "LIQUIDITY_VANISH"
    MANUAL = "MANUAL"


class KillSwitchEvent(BaseModel):
    state: KillSwitchState
    reason: TriggerReason
    detail: str
    portfolio_usdt: float = 0.0
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class RiskSnapshot(BaseModel):
    """Point-in-time risk state of the portfolio."""
    risk_score: float                    # 0–100 (higher = safer)
    mode: KillSwitchState
    exposure_pct: float                  # total open exposure as % of capital
    open_positions: int
    kill_switch_active: bool
    unrealized_pnl: float
    daily_pnl: float
    consecutive_losses: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AnomalyEvent(BaseModel):
    anomaly_type: str
    symbol: str
    detail: str
    severity: str                        # LOW / MEDIUM / HIGH / CRITICAL
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AuditDecision(BaseModel):
    approved: bool
    reason: str
    confidence_score: float
    regime: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
