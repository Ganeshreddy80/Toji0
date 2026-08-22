"""Thread-safe state storage for the Portfolio Construction Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import uuid
from typing import Dict, Optional

from portfolio_construction.core.interfaces import IPortfolioConstructionStateStore
from portfolio_construction.core.models import (
    PortfolioConstructionSnapshot,
    PortfolioConstructionState,
    TargetPortfolio,
)
from portfolio_construction.core.enums import PortfolioDecision

logger = logging.getLogger(__name__)


class PortfolioConstructionStateStore(IPortfolioConstructionStateStore):
    """Thread-safe in-memory state store for portfolio construction decisions."""

    def __init__(self, history_limit: int = 100) -> None:
        self._lock = threading.Lock()
        self._history_limit = history_limit
        self._states: Dict[str, PortfolioConstructionState] = {}
        self._correlation_matrices: Dict[str, Dict[str, Dict[str, float]]] = {}

    def update_state(self, state_update: PortfolioConstructionState) -> PortfolioConstructionSnapshot:
        """Store or update portfolio construction state thread-safely."""
        with self._lock:
            symbol = state_update.symbol
            prev_state = self._states.get(symbol)

            history = list(prev_state.history) if prev_state else []
            if state_update.active_portfolio and state_update.active_portfolio.decision != PortfolioDecision.HOLD:
                history.append(state_update.active_portfolio)
                if len(history) > self._history_limit:
                    history = history[-self._history_limit :]

            new_state = PortfolioConstructionState(
                symbol=symbol,
                active_portfolio=state_update.active_portfolio,
                history=history,
                updated_at=datetime.now(timezone.utc),
            )
            self._states[symbol] = new_state

            snapshot = PortfolioConstructionSnapshot(
                snapshot_id=str(uuid.uuid4()),
                timestamp=new_state.updated_at,
                state=new_state,
                correlation_matrix=self._correlation_matrices.get(symbol, {}),
            )
            logger.debug("PortfolioConstructionStateStore: Updated state for '%s'", symbol)
            return snapshot

    def get_state(self, symbol: str = "PORTFOLIO") -> Optional[PortfolioConstructionState]:
        """Fetch current portfolio construction state for a symbol."""
        with self._lock:
            return self._states.get(symbol)

    def set_correlation_matrix(self, symbol: str, matrix: Dict[str, Dict[str, float]]) -> None:
        """Store correlation matrix for a symbol."""
        with self._lock:
            self._correlation_matrices[symbol] = matrix

    def get_correlation_matrix(self, symbol: str = "PORTFOLIO") -> Dict[str, Dict[str, float]]:
        """Fetch correlation matrix for a symbol."""
        with self._lock:
            return dict(self._correlation_matrices.get(symbol, {}))

    def clear(self) -> None:
        """Clear all stored state."""
        with self._lock:
            self._states.clear()
            self._correlation_matrices.clear()
