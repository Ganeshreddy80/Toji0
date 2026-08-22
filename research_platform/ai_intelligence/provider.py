"""LLM Provider simulating API responses.
"""

from __future__ import annotations

from research_platform.ai_intelligence.interfaces import IAILlMProvider
from research_platform.ai_intelligence.models import AIRequest, AIResponse


class MockLLMProvider(IAILlMProvider):
    """Mock LLM adapter returning deterministic advisory responses."""

    def generate_text(self, request: AIRequest) -> AIResponse:
        """Call LLM API to get generated content text."""
        # Simple simulated explanation narrative
        text = (
            "Advisory Report:\n"
            "- Portfolio allocations look balanced.\n"
            "- Recommended Action: No changes needed. Keep leverage at 1.0x."
        )

        return AIResponse(
            text=text,
            confidence_score=0.95,
            reasoning_chain=["Check exposure limits", "Check VaR budgets", "Check health statuses"]
        )
