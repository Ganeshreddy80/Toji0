"""Confluence Engine Pydantic models."""

from __future__ import annotations

from typing import List
from pydantic import BaseModel


class ConfluenceResult(BaseModel):
    """Output results of institutional confluence scoring."""
    symbol: str
    score: float  # 0.0 to 100.0
    confidence: str  # "LOW", "MEDIUM", "HIGH"
    strength: str  # "STRONG", "WEAK"
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    explanations: List[str]
