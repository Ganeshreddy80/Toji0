"""PostgreSQL strategy repository.
"""

from __future__ import annotations

import json
from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import StrategyModel
from research_platform.strategy_lifecycle.models import StrategyStatus, StrategyAudit, StrategyApproval


class PostgresStrategyRepository(BaseRepository):
    """PostgreSQL-backed Strategy repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, StrategyModel)
        self._audits: dict[str, List[str]] = {}
        self._approvals: dict[str, List[str]] = {}

    def save_status(self, status: StrategyStatus) -> None:
        model = self.get(status.strategy_id)
        if model:
            updates = {
                "name": status.metadata.name,
                "status": status.status,
                "config": status.model_dump(mode="json")
            }
            self.update(status.strategy_id, updates)
        else:
            new_model = StrategyModel(
                strategy_id=status.strategy_id,
                name=status.metadata.name,
                status=status.status,
                config=status.model_dump(mode="json")
            )
            self.create(new_model)

    def get_status(self, strategy_id: str) -> Optional[StrategyStatus]:
        model = self.get(strategy_id)
        if model and model.config:
            return StrategyStatus.model_validate(model.config)
        return None

    def list_strategies(self, status_filter: Optional[str] = None) -> List[StrategyStatus]:
        filters = {}
        if status_filter:
            filters["status"] = status_filter
        models = self.list_all(filters=filters)
        results = []
        for m in models:
            if m.config:
                results.append(StrategyStatus.model_validate(m.config))
        return results

    def save_audit(self, audit: StrategyAudit) -> None:
        s_id = audit.strategy_id
        if s_id not in self._audits:
            self._audits[s_id] = []
        self._audits[s_id].append(audit.model_dump_json())

    def get_audit_history(self, strategy_id: str) -> List[StrategyAudit]:
        data = self._audits.get(strategy_id, [])
        return [StrategyAudit.model_validate_json(d) for d in data]

    def save_approval(self, approval: StrategyApproval) -> None:
        s_id = approval.strategy_id
        if s_id not in self._approvals:
            self._approvals[s_id] = []
        self._approvals[s_id].append(approval.model_dump_json())

    def list_approvals(self, strategy_id: str) -> List[StrategyApproval]:
        data = self._approvals.get(strategy_id, [])
        return [StrategyApproval.model_validate_json(d) for d in data]
