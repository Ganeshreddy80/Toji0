"""Multi Timeframe models for Toji."""

from __future__ import annotations

from typing import Dict, Any
from pydantic import BaseModel


class TimeframeBias(BaseModel):
    """Bias for a specific timeframe."""
    timeframe: str
    bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    strength: float  # 0.0 to 1.0


class TopDownAnalysis(BaseModel):
    """Result of top-down analysis across multiple timeframes."""
    symbol: str
    htf_bias: TimeframeBias
    mtf_bias: TimeframeBias
    ltf_bias: TimeframeBias
    aligned: bool
    final_bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
