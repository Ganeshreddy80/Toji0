"""Canonical Pydantic models for the Toji Intelligence Layer."""

from __future__ import annotations

from datetime import datetime, timezone
import enum
from pydantic import BaseModel, Field


class RiskGrade(enum.Enum):
    """Risk grade classification for market opportunities."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class AlertLevel(enum.Enum):
    """Priority level for system and market alerts."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Opportunity(BaseModel):
    """Represent an analyzed and ranked market trading opportunity."""

    symbol: str = Field(..., description="Target ticker symbol (e.g. BTC/USDT)")
    strategy_id: str = Field(..., description="ID of the strategy generating the opportunity")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall ranking score from 0.0 to 1.0")
    regime: str = Field(..., description="Current detected market regime phase")
    timing_window: str = Field(..., description="Execution window recommendation")
    risk_grade: RiskGrade = Field(..., description="Evaluated risk grade")
    evidence_count: int = Field(default=0, ge=0, description="Number of supporting evidence signals")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class Alert(BaseModel):
    """Represent a prioritized market or system alert."""

    alert_id: str = Field(..., description="Unique alert identifier")
    symbol: str = Field(..., description="Asset symbol triggering the alert")
    level: AlertLevel = Field(..., description="Severity level")
    title: str = Field(..., description="Summary of the alert event")
    message: str = Field(..., description="Detailed description or context")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class MarketPulse(BaseModel):
    """Aggregated real-time market health, sentiment, and risk indicators."""

    trend: float = Field(..., ge=-1.0, le=1.0, description="Normalized price trend (-1.0 to 1.0)")
    momentum: float = Field(..., ge=-1.0, le=1.0, description="Normalized momentum velocity (-1.0 to 1.0)")
    liquidity: float = Field(..., ge=0.0, description="Normalized liquidity ratio (depth relative to normal)")
    risk: float = Field(..., ge=0.0, le=1.0, description="Aggregated risk score (0.0 to 1.0)")
    volatility: float = Field(..., ge=0.0, description="Normalized volatility score (standard dev relative to normal)")
    participation: float = Field(..., ge=0.0, description="Volume/open interest participation ratio")
    fear: float = Field(..., ge=0.0, le=100.0, description="Fear & Greed style sentiment index (0 to 100)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall model or signal confidence (0.0 to 1.0)")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Synthesized market health rating (0.0 to 1.0)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
