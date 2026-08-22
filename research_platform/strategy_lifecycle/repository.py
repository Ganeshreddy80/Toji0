"""Strategy status state repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.strategy_lifecycle.interfaces import IStrategyRepository
from research_platform.strategy_lifecycle.models import StrategyStatus, StrategyAudit, StrategyApproval
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.strategy_repository import PostgresStrategyRepository


class StrategyRepository(IStrategyRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._strategies: Dict[str, StrategyStatus] = {}
        self._audits: Dict[str, List[StrategyAudit]] = {}
        self._approvals: Dict[str, List[StrategyApproval]] = {}

    def _get_pg_repo(self) -> Optional[PostgresStrategyRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresStrategyRepository(session_manager)
        return None

    def save_status(self, status: StrategyStatus) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_status(status)
            
        with self._lock:
            self._strategies[status.strategy_id] = status

    def get_status(self, strategy_id: str) -> Optional[StrategyStatus]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_status(strategy_id)
            
        with self._lock:
            return self._strategies.get(strategy_id)

    def list_strategies(self, status_filter: Optional[str] = None) -> List[StrategyStatus]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_strategies(status_filter)
            
        with self._lock:
            vals = list(self._strategies.values())
            if status_filter:
                return [s for s in vals if s.status == status_filter]
            return vals

    def save_audit(self, audit: StrategyAudit) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_audit(audit)
            
        with self._lock:
            s_id = audit.strategy_id
            if s_id not in self._audits:
                self._audits[s_id] = []
            self._audits[s_id].append(audit)

    def get_audit_history(self, strategy_id: str) -> List[StrategyAudit]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_audit_history(strategy_id)
            
        with self._lock:
            return list(self._audits.get(strategy_id, []))

    def save_approval(self, approval: StrategyApproval) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_approval(approval)

    def list_approvals(self, strategy_id: str) -> List[StrategyApproval]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_approvals(strategy_id)
            
        with self._lock:
            return list(self._approvals.get(strategy_id, []))
