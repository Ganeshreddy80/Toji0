from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from execution_engine.core.exceptions import RepositoryError
from execution_engine.core.interfaces import IExecutionRepository
from execution_engine.core.models import (
    ExecutionHealthSnapshot,
    ExecutionJournalEntry,
    ExecutionMetrics,
    ExecutionRequest,
    ExecutionResult,
    Order,
    OrderFill,
)

logger = logging.getLogger(__name__)


import threading

class ExecutionRepository(IExecutionRepository):
    """Persists and retrieves Execution Engine snapshots, sub-orders, journals, and transaction fills."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        
        # In-memory storage buffers
        self._requests: Dict[str, ExecutionRequest] = {}
        self._orders: Dict[str, Order] = {}
        self._fills: List[OrderFill] = []
        self._results: Dict[str, ExecutionResult] = {}
        self._journal_entries: List[ExecutionJournalEntry] = []
        self._health_snapshots: List[ExecutionHealthSnapshot] = []
        self._broker_logs: List[Dict[str, Any]] = []
        self._audit_records: List[Any] = []
        self._lock = threading.RLock()

    def save_request(self, request: ExecutionRequest) -> None:
        """Persist an incoming execution request."""
        with self._lock:
            self._requests[request.execution_id] = request
            if len(self._requests) > 1000:
                oldest = next(iter(self._requests))
                self._requests.pop(oldest, None)

        if self._storage:
            try:
                row = {
                    "execution_id": request.execution_id,
                    "request_id": request.request_id,
                    "symbol": request.symbol,
                    "timeframe": request.timeframe,
                    "timestamp": request.timestamp.isoformat(),
                    "data": request.model_dump_json(),
                }
                self._storage.write_rows("execution_requests", [row])
            except Exception as e:
                logger.error("Repository: Failed to save request: %s", e)
                raise RepositoryError(f"Failed to persist request to database: {e}") from e

    def save_order(self, order: Order) -> None:
        """Persist a broker-level order state update."""
        with self._lock:
            self._orders[order.client_order_id] = order
            if len(self._orders) > 1000:
                oldest = next(iter(self._orders))
                self._orders.pop(oldest, None)

        if self._storage:
            try:
                row = {
                    "client_order_id": order.client_order_id,
                    "execution_id": order.execution_id,
                    "broker_order_id": order.broker_order_id,
                    "state": order.state.value,
                    "updated_at": order.updated_at.isoformat(),
                    "data": order.model_dump_json(),
                }
                self._storage.write_rows("execution_orders", [row])
            except Exception as e:
                logger.error("Repository: Failed to save order: %s", e)
                raise RepositoryError(f"Failed to persist order to database: {e}") from e

    def save_fill(self, fill: OrderFill) -> None:
        """Persist transaction execution fill details."""
        with self._lock:
            self._fills.append(fill)
            if len(self._fills) > 1000:
                self._fills.pop(0)

        if self._storage:
            try:
                row = {
                    "fill_id": fill.fill_id,
                    "order_id": fill.order_id,
                    "client_order_id": fill.client_order_id,
                    "execution_id": fill.execution_id,
                    "timestamp": fill.timestamp.isoformat(),
                    "data": fill.model_dump_json(),
                }
                self._storage.write_rows("execution_fills", [row])
            except Exception as e:
                logger.error("Repository: Failed to save fill: %s", e)
                raise RepositoryError(f"Failed to persist fill to database: {e}") from e

    def save_result(self, result: ExecutionResult) -> None:
        """Persist final execution resolution details and metrics."""
        with self._lock:
            self._results[result.execution_id] = result
            if len(self._results) > 1000:
                oldest = next(iter(self._results))
                self._results.pop(oldest, None)

        if self._storage:
            try:
                row = {
                    "execution_id": result.execution_id,
                    "status": result.status.value,
                    "timestamp": result.timestamp.isoformat(),
                    "data": result.model_dump_json(),
                }
                self._storage.write_rows("execution_results", [row])
                
                # Persist metrics split-off if available
                if result.metrics:
                    m = result.metrics
                    m_row = {
                        "execution_id": m.execution_id,
                        "slippage": m.slippage,
                        "commission": m.commission,
                        "execution_duration_ms": m.execution_duration_ms,
                        "timestamp": m.timestamp.isoformat(),
                        "data": m.model_dump_json(),
                    }
                    self._storage.write_rows("execution_metrics", [m_row])
            except Exception as e:
                logger.error("Repository: Failed to save result/metrics: %s", e)
                raise RepositoryError(f"Failed to persist result to database: {e}") from e

    def save_journal_entry(self, entry: Any) -> None:
        """Append an entry into the immutable execution journal."""
        with self._lock:
            self._journal_entries.append(entry)
            if len(self._journal_entries) > 1000:
                self._journal_entries.pop(0)

        if self._storage:
            try:
                row = {
                    "journal_sequence_number": entry.journal_sequence_number,
                    "execution_id": entry.execution_id,
                    "new_state": entry.new_state.value,
                    "timestamp": entry.timestamp.isoformat(),
                    "data": entry.model_dump_json(),
                }
                self._storage.write_rows("execution_journal", [row])
            except Exception as e:
                logger.error("Repository: Failed to save journal entry: %s", e)
                raise RepositoryError(f"Failed to persist journal entry: {e}") from e

    def save_health_snapshot(self, snapshot: ExecutionHealthSnapshot) -> None:
        """Persist runtime diagnostics health status."""
        with self._lock:
            self._health_snapshots.append(snapshot)
            if len(self._health_snapshots) > 1000:
                self._health_snapshots.pop(0)

        if self._storage:
            try:
                row = {
                    "broker_connectivity": snapshot.broker_connectivity,
                    "queue_size": snapshot.queue_size,
                    "average_latency_ms": snapshot.average_latency_ms,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "data": snapshot.model_dump_json(),
                }
                self._storage.write_rows("execution_health", [row])
            except Exception as e:
                logger.error("Repository: Failed to save health snapshot: %s", e)
                raise RepositoryError(f"Failed to persist health snapshot: {e}") from e

    def save_broker_log(self, log_dict: Dict[str, Any]) -> None:
        """Persist raw broker response transaction log."""
        with self._lock:
            self._broker_logs.append(log_dict)
            if len(self._broker_logs) > 1000:
                self._broker_logs.pop(0)

        if self._storage:
            try:
                self._storage.write_rows("broker_logs", [log_dict])
            except Exception as e:
                logger.error("Repository: Failed to save broker log: %s", e)
                raise RepositoryError(f"Failed to persist broker log: {e}") from e

    def load_order(self, client_order_id: str) -> Optional[Order]:
        """Retrieve a specific order from local indexes or storage engine."""
        with self._lock:
            if client_order_id in self._orders:
                return self._orders[client_order_id]

        if self._storage:
            try:
                query = "SELECT data FROM execution_orders WHERE client_order_id = %s"
                rows = self._storage.execute(query, (client_order_id,))
                if rows:
                    raw_data = rows[0].get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    order = Order(**data_dict)
                    with self._lock:
                        self._orders[client_order_id] = order
                    return order
            except Exception as e:
                logger.error("Repository: Failed to load order: %s", e)
                raise RepositoryError(f"Failed to load order from database: {e}") from e

        return None

    def load_latest_orders(self, limit: int = 100) -> List[Order]:
        """Fetch latest processed orders sorted chronologically."""
        with self._lock:
            orders_list = list(self._orders.values())
        orders_list.sort(key=lambda o: o.created_at, reverse=True)
        return orders_list[:limit]

    def save_audit_record(self, record: Any) -> None:
        """Persist an immutable audit record."""
        with self._lock:
            self._audit_records.append(record)
            if len(self._audit_records) > 1000:
                self._audit_records.pop(0)
        if self._storage:
            try:
                row = {
                    "audit_id": record.audit_id,
                    "execution_id": record.execution_id,
                    "correlation_id": record.correlation_id,
                    "actor": record.actor,
                    "action": record.action,
                    "timestamp": record.timestamp.isoformat(),
                    "data": record.model_dump_json(),
                }
                self._storage.write_rows("execution_audit", [row])
            except Exception as e:
                logger.error("Repository: Failed to save audit record: %s", e)

    def get_audit_records(self, execution_id: Optional[str] = None) -> List[Any]:
        """Fetch audit records, optionally filtered by execution ID."""
        with self._lock:
            if execution_id:
                return [r for r in self._audit_records if r.execution_id == execution_id]
            return list(self._audit_records)
