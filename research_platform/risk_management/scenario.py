"""Stress Testing Scenario definitions.
"""

from __future__ import annotations

from research_platform.risk_management.models import StressScenario


class StressScenarios:
    """Built-in institutional crash scenarios parameters."""

    FLASH_CRASH = StressScenario(
        scenario_name="Flash Crash",
        volatility_shift=3.0,
        correlation_shift=0.5
    )

    BLACK_SWAN = StressScenario(
        scenario_name="Black Swan",
        volatility_shift=5.0,
        correlation_shift=0.8
    )
