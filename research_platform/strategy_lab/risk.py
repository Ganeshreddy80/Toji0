"""Pre-backtest Risk validation engine.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from research_platform.strategy_lab.models import StrategyDefinition, RiskRule


class StrategyRiskAuditor:
    """Audits strategy definitions for risk violations prior to running backtests."""

    @staticmethod
    def audit_strategy(strategy: StrategyDefinition) -> Tuple[bool, List[str]]:
        """Verify strategy configuration parameters against institutional risk limits.

        Checks:
            - MaxRiskPerTrade <= 0.05 (5% per trade cap)
            - SymbolConcentration <= 0.40 (40% symbol cap)
            - Leverage limits <= 5.0
        """
        violations = []

        for rule in strategy.risk_rules:
            if rule.limit_type == "MaxRiskPerTrade":
                if rule.value > 0.05:
                    violations.append(
                        f"Risk violation: {rule.name} risk value {rule.value:.2f} exceeds 5% trade cap."
                    )
            elif rule.limit_type == "SymbolConcentration":
                if rule.value > 0.40:
                    violations.append(
                        f"Risk violation: {rule.name} allocation concentration {rule.value:.2f} exceeds 40% cap."
                    )
            elif rule.limit_type == "LeverageLimits":
                if rule.value > 5.0:
                    violations.append(
                        f"Risk violation: {rule.name} leverage limit {rule.value:.2f} exceeds 5.0x cap."
                    )

        # Confirm sizing fractional allocation limits
        sizing_pct = strategy.sizing_rule.parameters.get("fraction", 0.0)
        if sizing_pct > 0.10:
            violations.append(
                f"Sizing violation: Sizing fractional risk {sizing_pct:.2f} exceeds 10% per-trade safety limit."
            )

        is_approved = len(violations) == 0
        return is_approved, violations
