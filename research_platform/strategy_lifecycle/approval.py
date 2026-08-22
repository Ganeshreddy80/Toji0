"""Approval engine managing Risk, AI, Human, and Committee governance checks.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from research_platform.strategy_lifecycle.interfaces import IApprovalEngine, IStrategyRepository
from research_platform.strategy_lifecycle.models import ApprovalRecord, LifecycleStage


class StrategyApprovalEngine(IApprovalEngine):
    """Logs and validates governance approvals for strategy promotions."""

    def __init__(self, repository: IStrategyRepository) -> None:
        self._repo = repository

    def record_approval(
        self,
        request_id: str,
        reviewer_type: str,
        reviewer: str,
        approved: bool,
        reason: str,
        evidence: Dict[str, Any],
        linked_report_id: Optional[str] = None
    ) -> ApprovalRecord:
        """Create and store an individual approval record."""
        request = self._repo.get_promotion_request(request_id)
        if not request:
            raise ValueError(f"Promotion request '{request_id}' not found.")

        # Determine stage based on target stage in request
        stage = request.target_stage

        record = ApprovalRecord(
            approval_id=f"app-{uuid.uuid4().hex[:8]}",
            request_id=request_id,
            stage=stage,
            reviewer_type=reviewer_type,
            reviewer=reviewer,
            approved=approved,
            reason=reason,
            evidence=evidence,
            linked_report_id=linked_report_id
        )

        self._repo.save_approval_record(record)
        return record

    def record_committee_approval(
        self,
        request_id: str,
        votes: Dict[str, bool],
        required_votes: int,
        reason: str,
        evidence: Dict[str, Any]
    ) -> ApprovalRecord:
        """Evaluate committee vote results and save a summary ApprovalRecord."""
        request = self._repo.get_promotion_request(request_id)
        if not request:
            raise ValueError(f"Promotion request '{request_id}' not found.")

        yes_votes = sum(1 for vote in votes.values() if vote)
        passed = yes_votes >= required_votes

        full_evidence = dict(evidence or {})
        full_evidence.update({
            "votes": votes,
            "total_votes_cast": len(votes),
            "yes_votes": yes_votes,
            "required_votes": required_votes
        })

        record = ApprovalRecord(
            approval_id=f"app-{uuid.uuid4().hex[:8]}",
            request_id=request_id,
            stage=request.target_stage,
            reviewer_type="COMMITTEE",
            reviewer="INVESTMENT_COMMITTEE",
            approved=passed,
            reason=reason,
            evidence=full_evidence,
            linked_report_id=None
        )

        self._repo.save_approval_record(record)
        return record
