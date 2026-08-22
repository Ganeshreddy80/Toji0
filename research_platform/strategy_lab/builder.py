"""Strategy Builder and Alpha-to-Strategy converter.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict

from research_platform.alpha_factory.models import AlphaCandidate
from research_platform.strategy_lab.models import (
    EntryRule,
    ExitRule,
    PositionSizingRule,
    RiskRule,
    StrategyDefinition,
    StrategyTemplate
)


class StrategyBuilder:
    """Provides converters and factory templates for generating StrategyDefinitions."""

    @staticmethod
    def convert_alpha_to_strategy(alpha: AlphaCandidate) -> StrategyDefinition:
        """Convert a validated alpha candidate factor into a fully defined StrategyDefinition."""
        # 1. Entry Rule targeting compiled alpha signal column
        entry = EntryRule(
            name="Alpha_Signal_Trigger",
            condition_type="SignalThreshold",
            parameters={
                "column": f"alpha_{alpha.candidate_id}",
                "threshold": 0.5,
                "operator": ">"
            }
        )

        # 2. Exit Rules: Stop Loss (2%) and Profit Target (5%)
        exit_sl = ExitRule(
            name="Default_Stop_Loss",
            condition_type="StopLoss",
            parameters={"stop_pct": 0.02}
        )
        exit_pt = ExitRule(
            name="Default_Profit_Target",
            condition_type="ProfitTarget",
            parameters={"target_pct": 0.05}
        )

        # 3. Position Sizing: Fixed fractional risk allocation (2% risk)
        sizing = PositionSizingRule(
            name="Sizer_2pct_Fractional",
            sizing_type="FixedFractional",
            parameters={"fraction": 0.02, "stop_pct": 0.02}
        )

        # 4. Risk constraints pre-backtest limits
        risk_per_trade = RiskRule(
            name="Max_Risk_Per_Trade_Limit",
            limit_type="MaxRiskPerTrade",
            value=0.02
        )
        risk_conc = RiskRule(
            name="Max_Concentration_Limit",
            limit_type="SymbolConcentration",
            value=0.30
        )

        return StrategyDefinition(
            strategy_id=str(uuid.uuid4()),
            name=f"Strategy_{alpha.candidate_id[:8]}",
            display_name=f"Strategy built from alpha factor {alpha.candidate_id[:8]}",
            description=f"Automated strategy mapping DSL: {alpha.expression.formula_str}",
            version="1.0.0",
            entry_rules=[entry],
            exit_rules=[exit_sl, exit_pt],
            sizing_rule=sizing,
            risk_rules=[risk_per_trade, risk_conc],
            status="DRAFT"
        )

    @staticmethod
    def load_template(template_name: str) -> StrategyTemplate:
        """Fetch pre-configured institutional templates."""
        entry = EntryRule(
            name="Template_Signal_Entry",
            condition_type="SignalThreshold",
            parameters={"column": "signal", "threshold": 0.0, "operator": ">"}
        )
        exit_sl = ExitRule(
            name="Template_Stop_Loss",
            condition_type="StopLoss",
            parameters={"stop_pct": 0.015}
        )
        sizing = PositionSizingRule(
            name="Template_Fixed_Sizing",
            sizing_type="FixedSize",
            parameters={"units": 10.0}
        )

        return StrategyTemplate(
            template_id=str(uuid.uuid4()),
            name=template_name,
            base_entry_rules=[entry],
            base_exit_rules=[exit_sl],
            base_sizing=sizing
        )
