"""Prompt Builder generating formatted LLM instructions.
"""

from __future__ import annotations

from typing import Any, Dict

from research_platform.ai_intelligence.models import AIRequest


class PromptBuilder:
    """Generates structured prompts using context and states."""

    @staticmethod
    def build_review_prompt(context: Dict[str, Any], task: str) -> AIRequest:
        """Format parameters into standard AIRequest structure."""
        prompt = (
            f"Please perform a {task} using the following operational details:\n"
            f"Portfolio Value: {context.get('portfolio_value')}\n"
            f"Net Exposure: {context.get('net_exposure')}\n"
            f"VaR Utilization: {context.get('var_utilization')}\n"
            f"Open Alerts: {context.get('open_alerts_count')}\n"
            f"System Health: {context.get('system_healthy')}\n"
        )

        return AIRequest(
            prompt=prompt,
            system_instruction="You are the Chief Investment Officer and Quant Research Assistant."
        )
