"""Immutable Pydantic models for the Alpha Factory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Any
from pydantic import BaseModel, ConfigDict, Field


class AlphaSignal(BaseModel):
    """An alpha signal representing direction and strength output from a factor."""

    signal_id: str
    factor_id: str
    direction: str  # BUY, SELL, FLAT
    strength: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AlphaCombo(BaseModel):
    """A weighted combination of factors details."""

    combo_id: str
    signals: List[AlphaSignal] = Field(default_factory=list)
    weights: List[float] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class EnsembleModel(BaseModel):
    """An ensemble model combining multiple factor combinations."""

    ensemble_id: str
    combos: List[AlphaCombo] = Field(default_factory=list)
    active: bool = True

    model_config = ConfigDict(frozen=True)
