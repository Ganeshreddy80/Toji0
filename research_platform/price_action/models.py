"""Price action structure Pydantic models for TOJI V1."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class SwingPoint(BaseModel):
    """Represents a swing high or swing low point."""
    point_type: str  # "HIGH" or "LOW"
    price: float
    timestamp: datetime
    index: int


class MarketStructureChange(BaseModel):
    """Represents a Break of Structure (BOS) or Change of Character (CHOCH)."""
    change_type: str  # "BOS" or "CHOCH"
    direction: str  # "BULLISH" or "BEARISH"
    break_price: float
    trigger_price: float
    timestamp: datetime


class LiquiditySweep(BaseModel):
    """Represents a liquidity sweep event."""
    sweep_type: str  # "HIGH" or "LOW"
    boundary_price: float
    sweep_price: float
    timestamp: datetime


class BlockStructure(BaseModel):
    """Represents an Order Block, Breaker Block, or Mitigation Block."""
    block_type: str  # "ORDER", "BREAKER", "MITIGATION"
    direction: str  # "BULLISH" or "BEARISH"
    high: float
    low: float
    volume: float
    timestamp: datetime
    mitigated: bool = False
    mitigated_timestamp: Optional[datetime] = None


class ImbalanceGap(BaseModel):
    """Represents a Fair Value Gap (FVG), Inverse FVG, or Volume Imbalance."""
    gap_type: str  # "FVG", "INVERSE_FVG", "VOLUME_IMBALANCE"
    high: float
    low: float
    timestamp: datetime
    filled: bool = False
    filled_timestamp: Optional[datetime] = None


class SessionPeriod(BaseModel):
    """Represents trading session window boundaries."""
    name: str  # "ASIA", "LONDON", "NEWYORK"
    start_time: datetime
    end_time: datetime
    high: float = 0.0
    low: float = 0.0
