"""Strategy Lab Orchestrator implementation.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.strategy_lab.interfaces import IStrategyLabOrchestrator
from research_platform.strategy_lab.models import StrategyDefinition
from research_platform.strategy_lab.registry import StrategyRegistry
from research_platform.strategy_lab.repository import StrategyRepository
from research_platform.strategy_lab.risk import StrategyRiskAuditor
from research_platform.strategy_lab.events import (
    StrategyApproved,
    StrategyCreated,
    StrategyExported,
    StrategyRejected,
    StrategyUpdated,
    StrategyValidated
)

logger = logging.getLogger(__name__)


class StrategyLabOrchestrator(IStrategyLabOrchestrator):
    """Coordinates manual and automated strategy builds, risk auditing, and backtest exporting."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = StrategyRepository()
        self._registry = StrategyRegistry()

    @property
    def repository(self) -> StrategyRepository:
        return self._repo

    @property
    def registry(self) -> StrategyRegistry:
        return self._registry

    def compose_strategy(self, definition: StrategyDefinition) -> StrategyDefinition:
        """Process and validate strategy composition before registration.

        Raises:
            ValueError: If risk limits or validation checks fail.
        """
        # 1. Structural checks (rules completeness)
        if not definition.entry_rules:
            self._event_bus.publish(StrategyRejected(payload={"strategy_id": definition.strategy_id, "reason": "Missing Entry rules"}))
            raise ValueError("Strategy definition must contain at least one EntryRule.")

        if not definition.exit_rules:
            self._event_bus.publish(StrategyRejected(payload={"strategy_id": definition.strategy_id, "reason": "Missing Exit rules"}))
            raise ValueError("Strategy definition must contain at least one ExitRule.")

        # 2. Institutional risk audit
        passed, violations = StrategyRiskAuditor.audit_strategy(definition)
        if not passed:
            self._event_bus.publish(
                StrategyRejected(
                    payload={
                        "strategy_id": definition.strategy_id,
                        "reason": f"Risk violations: {', '.join(violations)}"
                    }
                )
            )
            raise ValueError(f"Strategy violates risk parameters: {'; '.join(violations)}")

        # 3. Mark candidate as validated and persist
        validated_def = StrategyDefinition(
            strategy_id=definition.strategy_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            version=definition.version,
            entry_rules=definition.entry_rules,
            exit_rules=definition.exit_rules,
            sizing_rule=definition.sizing_rule,
            risk_rules=definition.risk_rules,
            status="VALIDATED",
            created_time=definition.created_time
        )

        self._repo.save(validated_def)
        self._registry.register(validated_def)

        # Publish events
        self._event_bus.publish(StrategyCreated(payload={"strategy_id": definition.strategy_id}))
        self._event_bus.publish(StrategyValidated(payload={"strategy_id": definition.strategy_id}))
        logger.info("Successfully composed and validated strategy definition: %s", definition.name)

        return validated_def

    def export_to_backtest(self, strategy_id: str) -> StrategyDefinition:
        """Export strategy candidate parameters to the Backtesting Engine."""
        strat = self._repo.get(strategy_id)
        if not strat:
            raise KeyError(f"Strategy definition '{strategy_id}' not found.")

        # Promote to APPROVED/EXPORTED
        approved_strat = StrategyDefinition(
            strategy_id=strat.strategy_id,
            name=strat.name,
            display_name=strat.display_name,
            description=strat.description,
            version=strat.version,
            entry_rules=strat.entry_rules,
            exit_rules=strat.exit_rules,
            sizing_rule=strat.sizing_rule,
            risk_rules=strat.risk_rules,
            status="APPROVED",
            created_time=strat.created_time
        )

        self._repo.save(approved_strat)
        self._registry.register(approved_strat)

        self._event_bus.publish(StrategyApproved(payload={"strategy_id": strategy_id}))
        self._event_bus.publish(StrategyExported(payload={"strategy_id": strategy_id}))
        logger.info("Exported approved Strategy definition %s to the Backtest Engine.", strategy_id)

        return approved_strat
