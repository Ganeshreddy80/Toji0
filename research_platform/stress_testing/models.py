"""Immutable Pydantic models for the Stress Testing Engine.
"""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, ConfigDict, Field


class StressScenario(BaseModel):
    """A stress testing scenario definition."""

    scenario_id: str
    name: str
    shock_type: str  # FLASH_CRASH, EXCHANGE_OUTAGE, BLACK_SWAN, VOL_SHOCK
    magnitude: float

    model_config = ConfigDict(frozen=True)


class StressRun(BaseModel):
    """Result of a stress scenario execution on portfolio."""

    run_id: str
    scenario_id: str
    initial_value: float
    shocked_value: float
    drawdown_pct: float

    model_config = ConfigDict(frozen=True)


class RecoveryPlan(BaseModel):
    """An estimated recovery plan for a distressed portfolio state."""

    run_id: str
    recovery_steps: List[str] = Field(default_factory=list)
    estimated_days: int

    model_config = ConfigDict(frozen=True)
