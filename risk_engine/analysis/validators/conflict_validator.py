"""Conflict Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class ConflictValidator:
    """Checks for conflicting indicators, high confluence penalties, or contradictory strategy signals."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        confluence_state = context.confluence_state
        strategy_signal = context.strategy_signal

        # 1. Check confluence conflict penalty
        if confluence_state and confluence_state.score:
            if confluence_state.score.conflict_penalty >= 4.0:
                return (
                    RiskFactor(
                        id="RE_CONF_001",
                        name="High Confluence Conflict Penalty",
                        severity=RiskSeverity.HIGH,
                        score=30.0,
                        description=f"Confluence engine reports a conflict penalty of {confluence_state.score.conflict_penalty:.2f} "
                        f"which exceeds the safety threshold of 4.00.",
                    ),
                    30.0,
                    f"High confluence conflict penalty: {confluence_state.score.conflict_penalty:.2f} >= 4.0.",
                )

            if confluence_state.score.overall_score < 50.0:
                return (
                    RiskFactor(
                        id="RE_CONF_002",
                        name="Weak Confluence Setup",
                        severity=RiskSeverity.MEDIUM,
                        score=20.0,
                        description=f"Confluence overall score of {confluence_state.score.overall_score:.2f} "
                        f"is below the minimum required score of 50.0.",
                    ),
                    20.0,
                    f"Weak confluence: {confluence_state.score.overall_score:.2f} < 50.0.",
                )

        # 2. Check strategy signal conflicting factors count
        if strategy_signal:
            if len(strategy_signal.conflicting_factors) >= 3:
                return (
                    RiskFactor(
                        id="RE_CONF_003",
                        name="Multiple Strategy Signal Conflicts",
                        severity=RiskSeverity.HIGH,
                        score=25.0,
                        description=f"Strategy signal reports {len(strategy_signal.conflicting_factors)} "
                        f"active conflicting factors.",
                    ),
                    25.0,
                    f"Strategy has multiple conflicts: count={len(strategy_signal.conflicting_factors)}.",
                )

        return None, 0.0, None
