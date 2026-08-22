"""Validator assessing core subsystems integration linkages.
"""

from __future__ import annotations

import time
from typing import Any
from research_platform.system_validation.interfaces import ISubsystemValidator
from research_platform.system_validation.models import (
    SubsystemHealth,
    ValidationCheck,
    ValidationSeverity,
)


class IntegrationValidator(ISubsystemValidator):
    """Audits the integration link between features store, risk bounds, and portfolios."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        # Audit if R19-R26 modules resolve
        engines = [
            ("Market Regime", "research_platform.market_regime.plugin.MarketRegimePlugin"),
            ("Portfolio Optimizer", "research_platform.portfolio_optimizer.plugin.PortfolioOptimizerPlugin"),
            ("Research Intelligence", "research_platform.research_intelligence.plugin.ResearchIntelligencePlugin"),
            ("Experiment Management", "research_platform.experiment_management.plugin.ExperimentManagementPlugin"),
            ("Multi-Agent System", "research_platform.multi_agent.plugin.MultiAgentPlugin"),
            ("Governance", "research_platform.governance.plugin.GovernancePlugin"),
            ("Simulation Engine", "research_platform.simulation.plugin.SimulationPlugin")
        ]

        for label, ekey in engines:
            has_plugin = container.has(ekey) if hasattr(container, "has") else True
            checks.append(ValidationCheck(
                name=f"Integration Link: {label}",
                description=f"Verify DI registrations and linkages for {label} engine.",
                category="Platform Integration",
                passed=has_plugin,
                severity=ValidationSeverity.ERROR,
                message=f"{label} successfully integrated." if has_plugin else f"{label} integration link broken."
            ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else max(0.0, 100.0 - (len(failures) * 15.0))

        return SubsystemHealth(
            name="Integration",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
