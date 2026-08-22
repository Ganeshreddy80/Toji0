"""Abstract contracts for the Digital Twin & Simulation Engine.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.simulation.models import (
    ReplayConfiguration,
    SimOrder,
    SimulationResult,
    SimTick,
)


class ISimulationRepository(abc.ABC):
    """Abstract contract for persisting configurations and simulation outcomes."""

    @abc.abstractmethod
    def save_configuration(self, config: ReplayConfiguration) -> None:
        """Persist simulation configuration settings."""

    @abc.abstractmethod
    def get_configuration(self, session_id: str) -> Optional[ReplayConfiguration]:
        """Retrieve simulation configuration settings by ID."""

    @abc.abstractmethod
    def save_order(self, order: SimOrder) -> None:
        """Persist a simulated order state record."""

    @abc.abstractmethod
    def list_orders(self, session_id: str) -> List[SimOrder]:
        """List orders logged during a session."""

    @abc.abstractmethod
    def save_result(self, result: SimulationResult) -> None:
        """Persist simulation summary stats results."""

    @abc.abstractmethod
    def get_result(self, session_id: str) -> Optional[SimulationResult]:
        """Retrieve results for a session ID."""


class IMarketReplayer(abc.ABC):
    """Abstract contract for historical tick replayers."""

    @abc.abstractmethod
    def replay_ticks(self, ticks: List[SimTick], config: ReplayConfiguration) -> List[SimTick]:
        """Feed price ticks sequentially applying volatility multipliers."""


class IExchangeSimulator(abc.ABC):
    """Abstract contract for order matching exchanges."""

    @abc.abstractmethod
    def match_order(self, order: SimOrder, tick: SimTick) -> SimOrder:
        """Match SimOrder against SimTick price feeds."""


class ISimulationOrchestrator(abc.ABC):
    """Abstract contract for the digital twin orchestrator."""
    pass
