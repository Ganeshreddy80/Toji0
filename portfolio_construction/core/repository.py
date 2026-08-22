"""Thread-safe Repository for Portfolio Construction Engine persistence."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from portfolio_construction.core.interfaces import IPortfolioConstructionRepository
from portfolio_construction.core.models import PortfolioConstructionSnapshot

logger = logging.getLogger(__name__)


class PortfolioConstructionRepository(IPortfolioConstructionRepository):
    """Thread-safe repository caching portfolio snapshots and correlation matrices."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._lock = threading.Lock()
        self._storage_engine = storage_engine
        self._snapshots: Dict[str, PortfolioConstructionSnapshot] = {}
        self._latest_by_symbol: Dict[str, str] = {}
        self._matrices: Dict[str, Dict[str, Dict[str, float]]] = {}

    def save_snapshot(self, snapshot: PortfolioConstructionSnapshot) -> None:
        """Persist a portfolio construction snapshot."""
        with self._lock:
            snap_id = snapshot.snapshot_id
            symbol = snapshot.state.symbol
            self._snapshots[snap_id] = snapshot
            self._latest_by_symbol[symbol] = snap_id

            if snapshot.correlation_matrix:
                self._matrices[symbol] = snapshot.correlation_matrix

            logger.debug("PortfolioConstructionRepository: Saved snapshot '%s' for '%s'", snap_id, symbol)

        if self._storage_engine is not None:
            try:
                self._persist_to_storage(snapshot)
            except Exception as e:
                logger.error("PortfolioConstructionRepository: Storage engine persist error: %s", e)

    def load_latest_snapshot(self, symbol: str = "PORTFOLIO") -> Optional[PortfolioConstructionSnapshot]:
        """Load the latest snapshot for a portfolio symbol."""
        with self._lock:
            snap_id = self._latest_by_symbol.get(symbol)
            if snap_id:
                return self._snapshots.get(snap_id)
            return None

    def get_snapshot(self, snapshot_id: str) -> Optional[PortfolioConstructionSnapshot]:
        """Fetch snapshot by unique snapshot_id."""
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def save_correlation_matrix(self, symbol: str, matrix: Dict[str, Dict[str, float]]) -> None:
        """Persist correlation matrix data for a symbol."""
        with self._lock:
            self._matrices[symbol] = matrix

    def get_correlation_matrix(self, symbol: str = "PORTFOLIO") -> Optional[Dict[str, Dict[str, float]]]:
        """Retrieve correlation matrix data for a symbol."""
        with self._lock:
            return self._matrices.get(symbol)

    def _persist_to_storage(self, snapshot: PortfolioConstructionSnapshot) -> None:
        """Internal helper to write to storage engine if present."""
        if hasattr(self._storage_engine, "execute"):
            query = """
                INSERT INTO portfolio_construction_snapshots (snapshot_id, symbol, timestamp, state_json, correlation_matrix_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_id) DO UPDATE SET state_json = EXCLUDED.state_json;
            """
            self._storage_engine.execute(
                query,
                (
                    snapshot.snapshot_id,
                    snapshot.state.symbol,
                    snapshot.timestamp,
                    snapshot.state.model_dump_json(),
                    str(snapshot.correlation_matrix),
                ),
            )
