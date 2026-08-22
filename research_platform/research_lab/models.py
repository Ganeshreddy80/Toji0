"""Immutable Pydantic models for the Research Lab.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Any
from pydantic import BaseModel, ConfigDict, Field


class FeatureData(BaseModel):
    """Extracted feature datasets."""

    feature_id: str
    values: List[float] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class AlphaFactor(BaseModel):
    """Calculated alpha factors formulas."""

    factor_id: str
    formula: str
    values: List[float] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class Indicator(BaseModel):
    """Simple indicators definitions catalog."""

    indicator_id: str
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class Hypothesis(BaseModel):
    """Hypothesis tracking details."""

    hypothesis_id: str
    description: str
    p_value: float
    verified: bool

    model_config = ConfigDict(frozen=True)


class ResearchSession(BaseModel):
    """Active quant research sessions cards."""

    session_id: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
