"""Models and schema definitions for the Exit Engine.
"""

from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field


class ExitEngineConfig(BaseModel):
    """Configuration options for Exit Engine rules, sourced from environment variables."""

    stop_loss_pct: Optional[float] = Field(default=None, description="Stop loss as ratio (e.g. 0.02 for 2%)")
    take_profit_pct: Optional[float] = Field(default=None, description="Take profit as ratio (e.g. 0.05 for 5%)")
    trailing_pct: Optional[float] = Field(default=None, description="Trailing stop distance as ratio (e.g. 0.02 for 2%)")
    break_even_trigger_pct: Optional[float] = Field(default=None, description="Profit threshold to activate breakeven (e.g. 0.03 for 3%)")
    time_stop_seconds: Optional[float] = Field(default=None, description="Max holding duration in seconds")
    atr_multiplier: Optional[float] = Field(default=None, description="ATR multiplier for ATR-based stops")
    volatility_threshold: Optional[float] = Field(default=None, description="Volatility exit threshold on normalized ATR")
    risk_score_threshold: Optional[float] = Field(default=None, description="Risk score threshold to trigger emergency exits")


class PositionExitState(BaseModel):
    """Mutable exit-related tracking indicators for an active position."""

    symbol: str
    initial_atr_stop: Optional[float] = None
    trailing_stop_level: Optional[float] = None
    break_even_activated: bool = False
    exit_requested: bool = False
    exit_reason: Optional[str] = None
