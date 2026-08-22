"""Account Manager synchronizing balance margins and buying power metrics.
"""

from __future__ import annotations

from typing import Dict

from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator


class AccountManager:
    """Manages buying power, cash balances, and updates via EMS adapters."""

    def __init__(self, ems: ExecutionEngineOrchestrator) -> None:
        self.ems = ems
        self._available_cash = 0.0
        self._total_equity = 0.0
        self._margin_used = 0.0

    def sync_balances(self, exchange: str) -> None:
        """Query balances from EMS adapter endpoints."""
        adapter = self.ems._router.get_adapter(exchange)
        balances = adapter.get_balances()
        positions = adapter.get_positions()

        # Simple mapping calculations
        for bal in balances:
            if bal.asset == "USDT":
                self._available_cash = bal.free
                self._total_equity = bal.total

        self._margin_used = sum(pos.margin_requirement for pos in positions)

    @property
    def available_cash(self) -> float:
        return self._available_cash

    @property
    def total_equity(self) -> float:
        return self._total_equity

    @property
    def margin_utilization(self) -> float:
        if self._total_equity == 0.0:
            return 0.0
        return self._margin_used / self._total_equity
