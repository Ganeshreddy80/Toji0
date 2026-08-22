"""PostgreSQL-backed portfolio engine repository with memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.portfolio_engine.interfaces import IPortfolioRepository
from research_platform.portfolio_engine.models import (
    AllocationResult,
    Portfolio,
    PortfolioSnapshot,
    RebalancePlan
)
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.portfolio_repository import PostgresPortfolioRepository


class PortfolioRepository(IPortfolioRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._portfolios: Dict[str, Portfolio] = {}
        self._snapshots: Dict[str, List[PortfolioSnapshot]] = {}
        self._allocations: Dict[str, List[AllocationResult]] = {}
        self._rebalance_plans: Dict[str, List[RebalancePlan]] = {}

    def _get_pg_repo(self) -> Optional[PostgresPortfolioRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresPortfolioRepository(session_manager)
        return None

    def save_portfolio(self, portfolio: Portfolio) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_portfolio(portfolio)
            
        with self._lock:
            self._portfolios[portfolio.portfolio_id] = portfolio

    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_portfolio(portfolio_id)
            
        with self._lock:
            return self._portfolios.get(portfolio_id)

    def save_snapshot(self, portfolio_id: str, snapshot: PortfolioSnapshot) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_snapshot(portfolio_id, snapshot)
            
        with self._lock:
            if portfolio_id not in self._snapshots:
                self._snapshots[portfolio_id] = []
            self._snapshots[portfolio_id].append(snapshot)

    def list_snapshots(self, portfolio_id: str) -> List[PortfolioSnapshot]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_snapshots(portfolio_id)
            
        with self._lock:
            return list(self._snapshots.get(portfolio_id, []))

    def save_allocation(self, portfolio_id: str, alloc: AllocationResult) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_allocation(portfolio_id, alloc)
            
        with self._lock:
            if portfolio_id not in self._allocations:
                self._allocations[portfolio_id] = []
            self._allocations[portfolio_id].append(alloc)

    def save_rebalance_plan(self, portfolio_id: str, plan: RebalancePlan) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_rebalance_plan(portfolio_id, plan)
            
        with self._lock:
            if portfolio_id not in self._rebalance_plans:
                self._rebalance_plans[portfolio_id] = []
            self._rebalance_plans[portfolio_id].append(plan)
