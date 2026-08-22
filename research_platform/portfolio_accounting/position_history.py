"""Position History — complete lifecycle timeline for each position."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Dict, List

from research_platform.portfolio_accounting.models import PositionHistoryEntry

logger = logging.getLogger(__name__)


class PositionHistory:
    """Stores ordered timeline of PositionHistoryEntry events per symbol."""

    def __init__(self) -> None:
        self._timeline: Dict[str, List[PositionHistoryEntry]] = defaultdict(list)
        self._lock = threading.RLock()

    def append(self, entry: PositionHistoryEntry) -> None:
        with self._lock:
            self._timeline[entry.symbol].append(entry)

    def get(self, symbol: str) -> List[PositionHistoryEntry]:
        with self._lock:
            return list(self._timeline.get(symbol, []))

    def get_all(self) -> Dict[str, List[PositionHistoryEntry]]:
        with self._lock:
            return {s: list(entries) for s, entries in self._timeline.items()}

    def summary(self, symbol: str) -> dict:
        """Return a concise summary dict for API consumption."""
        entries = self.get(symbol)
        if not entries:
            return {"symbol": symbol, "events": 0}
        open_entry = next((e for e in entries if e.event_type == "OPEN"), None)
        close_entry = next((e for e in reversed(entries) if e.event_type == "CLOSE"), None)
        return {
            "symbol": symbol,
            "events": len(entries),
            "opened_at": open_entry.timestamp.isoformat() if open_entry else None,
            "closed_at": close_entry.timestamp.isoformat() if close_entry else None,
            "final_realized_pnl": close_entry.realized_pnl if close_entry else None,
        }
