"""Module registry tracking active platform components.
"""

from __future__ import annotations

from typing import Dict, List


class ModuleRegistry:
    """Aggregates active platform component module identifiers."""

    def __init__(self) -> None:
        self._modules: Dict[str, str] = {
            "kernel": "toji_platform.kernel",
            "oms": "research_platform.oms",
            "trade_journal": "research_platform.trade_journal",
            "portfolio_analytics": "research_platform.portfolio_analytics",
            "scheduler": "research_platform.scheduler",
            "research_lab": "research_platform.research_lab",
            "alpha_factory": "research_platform.alpha_factory",
            "walk_forward": "research_platform.walk_forward",
            "portfolio_construction": "research_platform.portfolio_construction",
            "execution_simulator": "research_platform.execution_simulator",
            "stress_testing": "research_platform.stress_testing",
            "monitoring": "research_platform.monitoring",
            "reporting": "research_platform.reporting"
        }

    def get_module_path(self, module_name: str) -> Optional[str]:
        return self._modules.get(module_name)

    def list_modules(self) -> List[str]:
        return list(self._modules.keys())
from typing import Optional
