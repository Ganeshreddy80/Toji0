"""Snapshot persistence repository for the Market Intelligence Layer."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from market_intelligence.core.exceptions import RepositoryException
from market_intelligence.core.interfaces import IRepository
from market_intelligence.core.models import (
    MarketSnapshot,
    ReplayReport,
    PerformanceReport,
    HealthReport,
)

logger = logging.getLogger(__name__)


import threading

class MarketIntelligenceRepository(IRepository):
    """Persist and retrieve Market Intelligence snapshots.

    Uses an in-memory database by default for dev/test/replay,
    and supports optional SQL storage backends for persistence.
    """

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        # In-memory indices
        self._by_id: dict[str, MarketSnapshot] = {}
        # symbol -> list of snapshots sorted chronologically
        self._by_symbol: dict[str, list[MarketSnapshot]] = {}

        # Sprint 5 report tables in-memory
        self._latest_replay_reports: dict[str, ReplayReport] = {}
        self._replay_reports: list[ReplayReport] = []
        self._latest_perf_reports: dict[str, PerformanceReport] = {}
        self._perf_reports: list[PerformanceReport] = []
        self._latest_health_report: HealthReport | None = None
        self._health_reports: list[HealthReport] = []
        self._lock = threading.RLock()

    def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Persist a market snapshot.

        Indexes in-memory and writes to storage backend if available.
        """
        if not snapshot.snapshot_id or not snapshot.symbol:
            raise RepositoryException("Snapshot must contain a valid ID and symbol.")

        # 1. Update in-memory indices
        with self._lock:
            self._by_id[snapshot.snapshot_id] = snapshot

            symbol = snapshot.symbol
            if symbol not in self._by_symbol:
                self._by_symbol[symbol] = []

            # Maintain sorted chronological order
            snapshots_list = self._by_symbol[symbol]
            snapshots_list.append(snapshot)
            snapshots_list.sort(key=lambda s: s.timestamp)
            if len(snapshots_list) > 1000:
                removed = snapshots_list.pop(0)
                self._by_id.pop(removed.snapshot_id, None)

        # 2. Persist to storage backend if provided
        if self._storage:
            try:
                row = {
                    "snapshot_id": snapshot.snapshot_id,
                    "symbol": snapshot.symbol,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "data": snapshot.model_dump_json(),
                }
                self._storage.write_rows("market_intelligence_snapshots", [row])
            except Exception as e:
                logger.error("Repository: Failed to write snapshot row: %s", e)
                raise RepositoryException(f"Failed to persist snapshot to storage engine: {e}") from e

        logger.debug(
            "Repository: Saved snapshot '%s' for symbol '%s' at timestamp %s",
            snapshot.snapshot_id,
            snapshot.symbol,
            snapshot.timestamp,
        )

    def load_snapshot(self, snapshot_id: str) -> MarketSnapshot | None:
        """Load a specific market snapshot by its unique ID."""
        # 1. Check in-memory index
        with self._lock:
            if snapshot_id in self._by_id:
                return self._by_id[snapshot_id]

        # 2. Check storage backend if available
        if self._storage:
            try:
                # Mock query parsing supports key match in execute
                query = f"SELECT data FROM market_intelligence_snapshots WHERE snapshot_id = '{snapshot_id}'"
                rows = self._storage.execute(query)
                if rows:
                    raw_data = rows[0].get("data")
                    if isinstance(raw_data, str):
                        data_dict = json.loads(raw_data)
                    else:
                        data_dict = raw_data
                    snapshot = MarketSnapshot(**data_dict)
                    # Cache in-memory
                    with self._lock:
                        self._by_id[snapshot_id] = snapshot
                    return snapshot
            except Exception as e:
                logger.error("Repository: Failed to load snapshot %s: %s", snapshot_id, e)
                raise RepositoryException(f"Failed to load snapshot from storage engine: {e}") from e

        return None

    def load_latest_snapshot(self, symbol: str) -> MarketSnapshot | None:
        """Load the most recent snapshot for a given symbol."""
        # 1. Check in-memory index
        with self._lock:
            snapshots_list = self._by_symbol.get(symbol)
            if snapshots_list:
                return snapshots_list[-1]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = (
                    f"SELECT data FROM market_intelligence_snapshots WHERE symbol = '{symbol}' "
                    "ORDER BY timestamp DESC LIMIT 1"
                )
                rows = self._storage.execute(query)
                if rows:
                    # Find latest from returned rows
                    latest_row = max(
                        rows,
                        key=lambda r: datetime.fromisoformat(r.get("timestamp", ""))
                        if isinstance(r.get("timestamp"), str)
                        else r.get("timestamp"),
                    )
                    raw_data = latest_row.get("data")
                    if isinstance(raw_data, str):
                        data_dict = json.loads(raw_data)
                    else:
                        data_dict = raw_data
                    snapshot = MarketSnapshot(**data_dict)
                    return snapshot
            except Exception as e:
                logger.error("Repository: Failed to load latest snapshot for %s: %s", symbol, e)
                raise RepositoryException(f"Failed to load latest snapshot from storage engine: {e}") from e

        return None

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketSnapshot]:
        """Load historical snapshots for a symbol over a specific timeframe."""
        results: list[MarketSnapshot] = []

        # 1. Load from storage engine if available
        if self._storage:
            try:
                query = (
                    f"SELECT data, timestamp FROM market_intelligence_snapshots WHERE symbol = '{symbol}' "
                    f"AND timestamp >= '{start.isoformat()}' AND timestamp <= '{end.isoformat()}'"
                )
                rows = self._storage.execute(query)
                for row in rows:
                    raw_data = row.get("data")
                    if isinstance(raw_data, str):
                        data_dict = json.loads(raw_data)
                    else:
                        data_dict = raw_data
                    snapshot = MarketSnapshot(**data_dict)
                    if start <= snapshot.timestamp <= end:
                        results.append(snapshot)
                results.sort(key=lambda s: s.timestamp)
                return results
            except Exception as e:
                logger.error(
                    "Repository: Failed to load historical snapshots for %s: %s", symbol, e
                )
                raise RepositoryException(f"Failed to load historical snapshots from storage engine: {e}") from e

        # 2. Fall back to in-memory index
        with self._lock:
            snapshots_list = self._by_symbol.get(symbol)
            if snapshots_list:
                for snapshot in snapshots_list:
                    if start <= snapshot.timestamp <= end:
                        results.append(snapshot)

        return results

    def save_replay_report(self, report: ReplayReport) -> None:
        """Persist a replay verification report."""
        symbol = report.symbol
        with self._lock:
            self._latest_replay_reports[symbol] = report
            self._replay_reports.append(report)
            if len(self._replay_reports) > 1000:
                self._replay_reports.pop(0)

        if self._storage:
            try:
                row = {
                    "report_id": report.report_id,
                    "symbol": report.symbol,
                    "timestamp": report.timestamp.isoformat(),
                    "data": report.model_dump_json(),
                }
                self._storage.write_rows("market_intelligence_replay_reports", [row])
            except Exception as e:
                logger.error("Repository: Failed to write replay report: %s", e)

    def save_performance_report(self, report: PerformanceReport) -> None:
        """Persist a performance benchmark report."""
        symbol = report.symbol
        with self._lock:
            self._latest_perf_reports[symbol] = report
            self._perf_reports.append(report)
            if len(self._perf_reports) > 1000:
                self._perf_reports.pop(0)

        if self._storage:
            try:
                row = {
                    "report_id": report.report_id,
                    "symbol": report.symbol,
                    "timestamp": report.timestamp.isoformat(),
                    "data": report.model_dump_json(),
                }
                self._storage.write_rows("market_intelligence_performance_reports", [row])
            except Exception as e:
                logger.error("Repository: Failed to write performance report: %s", e)

    def save_health_report(self, report: HealthReport) -> None:
        """Persist a subsystem health report."""
        with self._lock:
            self._latest_health_report = report
            self._health_reports.append(report)
            if len(self._health_reports) > 1000:
                self._health_reports.pop(0)

        if self._storage:
            try:
                row = {
                    "timestamp": report.timestamp.isoformat(),
                    "data": report.model_dump_json(),
                }
                self._storage.write_rows("market_intelligence_health_reports", [row])
            except Exception as e:
                logger.error("Repository: Failed to write health report: %s", e)

    def load_latest_replay_report(self, symbol: str) -> ReplayReport | None:
        """Load the latest replay report for a given symbol."""
        if self._storage:
            try:
                query = (
                    f"SELECT data FROM market_intelligence_replay_reports WHERE symbol = '{symbol}' "
                    "ORDER BY timestamp DESC LIMIT 1"
                )
                rows = self._storage.execute(query)
                if rows:
                    raw_data = rows[0].get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    return ReplayReport(**data_dict)
            except Exception as e:
                logger.error("Repository: Failed to load latest replay report for %s: %s", symbol, e)
        with self._lock:
            return self._latest_replay_reports.get(symbol)

    def load_latest_performance_report(self, symbol: str) -> PerformanceReport | None:
        """Load the latest performance report for a given symbol."""
        if self._storage:
            try:
                query = (
                    f"SELECT data FROM market_intelligence_performance_reports WHERE symbol = '{symbol}' "
                    "ORDER BY timestamp DESC LIMIT 1"
                )
                rows = self._storage.execute(query)
                if rows:
                    raw_data = rows[0].get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    return PerformanceReport(**data_dict)
            except Exception as e:
                logger.error("Repository: Failed to load latest performance report for %s: %s", symbol, e)
        with self._lock:
            return self._latest_perf_reports.get(symbol)

