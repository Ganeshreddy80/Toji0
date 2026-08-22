"""Interfaces and protocols for the Risk Engine subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment, RiskState, RiskSnapshot, RiskFactor


class IRiskEngine(Protocol):
    """Protocol for executing deterministic risk rules and consolidating scores."""

    def evaluate(self, context: TradingContext, **kwargs: Any) -> RiskAssessment:
        """Evaluate a trading context against all risk rules."""
        ...

    def evaluate_execution_request(self, request: Any, **kwargs: Any) -> RiskAssessment:
        """Evaluate an execution request against all risk check rules before broker routing."""
        ...


class IRiskRepository(Protocol):
    """Protocol for persistent storage and retrieval of Risk snapshots."""

    def save_snapshot(self, snapshot: RiskSnapshot) -> None:
        """Persist a risk snapshot."""
        ...

    def load_snapshot(self, snapshot_id: str) -> RiskSnapshot | None:
        """Load a specific risk snapshot by its ID."""
        ...

    def load_latest_snapshot(self, symbol: str) -> RiskSnapshot | None:
        """Load the most recent risk snapshot for a symbol."""
        ...

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[RiskSnapshot]:
        """Load historical risk snapshots over a time window."""
        ...


class IRiskStateStore(Protocol):
    """Protocol for the thread-safe active state store of risk snapshot results."""

    def get_snapshot(self, symbol: str) -> RiskSnapshot | None:
        """Retrieve the active risk snapshot for a symbol."""
        ...

    def update_snapshot(self, snapshot: RiskSnapshot) -> None:
        """Update the active risk snapshot."""
        ...

    def get_history(self, symbol: str, limit: int = 100) -> list[RiskSnapshot]:
        """Retrieve the in-memory history of snapshots."""
        ...

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: RiskState
    ) -> RiskSnapshot:
        """Update a specific timeframe's risk state on the active snapshot."""
        ...

    def clear(self) -> None:
        """Purge all tracked states from memory."""
        ...


class IRiskValidator(Protocol):
    """Protocol for individual risk rule checks in the Risk Engine."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        """Runs the validator. Returns (RiskFactor (if rule violated/checked), Penalty, Reason)."""
        ...
