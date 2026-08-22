"""Abstract contracts for the Live Trading Engine.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.live_trading.models import (
    ActiveSignal,
    LiveTradingSession,
    OpenPosition,
    RecoveryCheckpoint
)


class ISessionScheduler(abc.ABC):
    """Abstract contract for scheduling continuous loops."""

    @abc.abstractmethod
    def start_scheduler(self) -> None:
        """Start scheduler intervals."""

    @abc.abstractmethod
    def stop_scheduler(self) -> None:
        """Stop scheduler loops gracefully."""


class ISignalProcessor(abc.ABC):
    """Abstract contract for filtering real-time alpha signals."""

    @abc.abstractmethod
    def process_signal(self, signal: ActiveSignal) -> bool:
        """Filter duplicate signals, returns True if signal is valid."""


class IPositionManager(abc.ABC):
    """Abstract contract for managing open asset positions."""

    @abc.abstractmethod
    def update_position(self, symbol: str, quantity: float, price: float) -> OpenPosition:
        """Update position quantity and average price."""

    @abc.abstractmethod
    def get_position(self, symbol: str) -> Optional[OpenPosition]:
        """Fetch open position details by symbol."""


class IRecoveryManager(abc.ABC):
    """Abstract contract for loading checkpoints upon restart."""

    @abc.abstractmethod
    def save_checkpoint(self, checkpoint: RecoveryCheckpoint) -> None:
        """Save recovery state checkpoint."""

    @abc.abstractmethod
    def recover_state(self, session_id: str) -> Optional[RecoveryCheckpoint]:
        """Recover state checkpoint details."""
class ILiveTradingOrchestrator(abc.ABC):
    """Abstract contract for live trading orchestrator."""
    pass
