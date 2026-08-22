"""Abstract contracts for the AI Quant Intelligence Engine.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional

from research_platform.ai_intelligence.models import (
    AIRequest,
    AIResponse,
    JournalEntry,
    Recommendation,
    StrategyReview
)


class IAILlMProvider(abc.ABC):
    """Abstract contract for LLM provider adapters."""

    @abc.abstractmethod
    def generate_text(self, request: AIRequest) -> AIResponse:
        """Call LLM API to get generated content text."""


class IAIContextBuilder(abc.ABC):
    """Abstract contract for gathering operational details."""

    @abc.abstractmethod
    def gather_context(self) -> Dict[str, Any]:
        """Aggregate stats from risk limits, portfolio, OMS and EMS."""


class IAIMemory(abc.ABC):
    """Abstract contract for sliding retention memory logs."""

    @abc.abstractmethod
    def record_event(self, key: str, value: Any) -> None:
        """Record trade event or alert log."""
class IAIOrchestrator(abc.ABC):
    """Abstract contract for AI orchestrator."""
    pass
