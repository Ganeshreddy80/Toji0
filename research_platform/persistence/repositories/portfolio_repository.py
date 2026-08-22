"""PostgreSQL portfolio repository.
"""

from __future__ import annotations

import json
from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import PortfolioModel
from research_platform.portfolio_engine.models import Portfolio, PortfolioSnapshot, AllocationResult, RebalancePlan


class PostgresPortfolioRepository(BaseRepository):
    """PostgreSQL-backed Portfolio repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, PortfolioModel)
        self._snapshots: dict[str, List[str]] = {}
        self._allocations: dict[str, List[str]] = {}
        self._rebalance_plans: dict[str, List[str]] = {}

    def save_portfolio(self, portfolio: Portfolio) -> None:
        serialized = portfolio.model_dump_json()
        model = self.get(portfolio.portfolio_id)
        if model:
            updates = {
                "weights": serialized,
                "last_rebalanced": None
            }
            self.update(portfolio.portfolio_id, updates)
        else:
            new_model = PortfolioModel(
                portfolio_id=portfolio.portfolio_id,
                weights=serialized,
                last_rebalanced=None
            )
            self.create(new_model)

    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        model = self.get(portfolio_id)
        if model and model.weights:
            # Under sqlite/postgres, model.weights is either a dict or a string depending on dialect/JSON type.
            # If it is a string/json representation, load it.
            if isinstance(model.weights, str):
                return Portfolio.model_validate_json(model.weights)
            elif isinstance(model.weights, dict):
                return Portfolio.model_validate(model.weights)
        return None

    def save_snapshot(self, portfolio_id: str, snapshot: PortfolioSnapshot) -> None:
        if portfolio_id not in self._snapshots:
            self._snapshots[portfolio_id] = []
        self._snapshots[portfolio_id].append(snapshot.model_dump_json())

    def list_snapshots(self, portfolio_id: str) -> List[PortfolioSnapshot]:
        data = self._snapshots.get(portfolio_id, [])
        return [PortfolioSnapshot.model_validate_json(d) for d in data]

    def save_allocation(self, portfolio_id: str, alloc: AllocationResult) -> None:
        if portfolio_id not in self._allocations:
            self._allocations[portfolio_id] = []
        self._allocations[portfolio_id].append(alloc.model_dump_json())

    def save_rebalance_plan(self, portfolio_id: str, plan: RebalancePlan) -> None:
        if portfolio_id not in self._rebalance_plans:
            self._rebalance_plans[portfolio_id] = []
        self._rebalance_plans[portfolio_id].append(plan.model_dump_json())
