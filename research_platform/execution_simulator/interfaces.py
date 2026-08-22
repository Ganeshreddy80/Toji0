"""Abstract contracts for the Execution Simulator.
"""

from __future__ import annotations

import abc
from typing import Optional
from research_platform.execution_simulator.models import SimulatedExecution


class IExecutionSimulatorRepository(abc.ABC):
    """Abstract contract for persisting simulated executions."""

    @abc.abstractmethod
    def save_execution(self, execution: SimulatedExecution) -> None:
        """Persist simulated execution outcome details."""

    @abc.abstractmethod
    def get_execution(self, execution_id: str) -> Optional[SimulatedExecution]:
        """Retrieve simulated execution by ID."""


class ISimulatorExecutionEngine(abc.ABC):
    """Abstract contract for execution simulator engine."""

    @abc.abstractmethod
    def simulate_order_execution(
        self,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str
    ) -> SimulatedExecution:
        """Simulate order execution matching with slippages, fees, latencies."""
