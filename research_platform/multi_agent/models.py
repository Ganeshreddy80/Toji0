"""Immutable Pydantic models for the Multi-Agent Decision System.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentType(str, Enum):
    RESEARCH = "RESEARCH"
    MARKET = "MARKET"
    PORTFOLIO = "PORTFOLIO"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    MEMORY = "MEMORY"
    KG = "KG"
    AI_REVIEWER = "AI_REVIEWER"


class AgentRequest(BaseModel):
    """The incoming query context mapping target variables for agents review."""

    session_id: str
    strategy_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class AgentProposal(BaseModel):
    """An individual agent's calculated decision advisory proposal details."""

    agent_type: AgentType
    confidence_score: float
    advisory_recommendations: Dict[str, Any] = Field(default_factory=dict)
    rationale: str

    model_config = ConfigDict(frozen=True)


class AgentConsensus(BaseModel):
    """The compiled consensus proposal aggregated from all specialized agent proposals."""

    session_id: str
    proposals: List[AgentProposal] = Field(default_factory=list)
    final_recommendation: Dict[str, Any] = Field(default_factory=dict)
    status: str = "APPROVED"  # APPROVED or REJECTED depending on consensus rules
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
