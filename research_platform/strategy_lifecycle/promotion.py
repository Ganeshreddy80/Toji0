"""Promotion engine enforcing state machine transitions and verifying required artifacts.
"""

from __future__ import annotations

import logging
from typing import List, Set
from research_platform.strategy_lifecycle.interfaces import IPromotionEngine
from research_platform.strategy_lifecycle.models import ApprovalRecord, LifecycleStage, PromotionRequest, Strategy, StrategyVersion

logger = logging.getLogger(__name__)


class StrategyPromotionEngine(IPromotionEngine):
    """Enforces state machine rules and validates artifacts completeness."""

    def __init__(self) -> None:
        # Define allowed transitions
        self._linear_flow = [
            LifecycleStage.DRAFT,
            LifecycleStage.RESEARCH,
            LifecycleStage.BACKTEST,
            LifecycleStage.WALK_FORWARD,
            LifecycleStage.PAPER_TRADING,
            LifecycleStage.RISK_REVIEW,
            LifecycleStage.AI_REVIEW,
            LifecycleStage.HUMAN_APPROVAL,
            LifecycleStage.READY_FOR_DEPLOYMENT,
            LifecycleStage.CANARY,
            LifecycleStage.LIVE,
            LifecycleStage.MONITORING
        ]

    def validate_promotion(
        self,
        strategy: Strategy,
        version: StrategyVersion,
        request: PromotionRequest,
        approvals: List[ApprovalRecord]
    ) -> bool:
        """Enforces state machine rules and checklist validations. Throws ValueError on violation."""
        source = request.source_stage
        target = request.target_stage

        if strategy.current_stage != source:
            raise ValueError(f"Strategy current stage is '{strategy.current_stage}', but request source is '{source}'.")

        # 1. State Machine Validity Checks
        valid = False

        # Rule A: Anyone can transition to Retired or Archived
        if target in (LifecycleStage.RETIRED, LifecycleStage.ARCHIVED):
            valid = True

        # Rule B: Linear flow transition
        elif source in self._linear_flow and target in self._linear_flow:
            try:
                src_idx = self._linear_flow.index(source)
                tgt_idx = self._linear_flow.index(target)
                if tgt_idx == src_idx + 1:
                    valid = True
            except ValueError:
                pass

        # Rule C: Pause exceptions
        elif target == LifecycleStage.PAUSED:
            if source in (LifecycleStage.CANARY, LifecycleStage.LIVE, LifecycleStage.MONITORING):
                valid = True

        # Rule D: Rollback exceptions
        elif target == LifecycleStage.ROLLBACK:
            if source in (LifecycleStage.PAUSED, LifecycleStage.MONITORING, LifecycleStage.LIVE):
                valid = True

        # Rule E: Resume or progress from Paused/Rollback
        elif source == LifecycleStage.PAUSED:
            if target in (LifecycleStage.LIVE, LifecycleStage.ROLLBACK, LifecycleStage.RETIRED):
                valid = True
        elif source == LifecycleStage.ROLLBACK:
            if target in (LifecycleStage.MONITORING, LifecycleStage.READY_FOR_DEPLOYMENT, LifecycleStage.PAUSED, LifecycleStage.RETIRED):
                valid = True

        if not valid:
            raise ValueError(f"Invalid state transition requested: {source} -> {target}")

        # 2. Artifact Checklist Validations
        if target == LifecycleStage.RESEARCH:
            pass  # No strict artifact requirements to enter research
            
        elif target == LifecycleStage.BACKTEST:
            if "research_report" not in request.artifacts:
                raise ValueError("Promotion to BACKTEST requires a 'research_report' artifact.")

        elif target == LifecycleStage.WALK_FORWARD:
            if "backtest_results" not in request.artifacts:
                raise ValueError("Promotion to WALK_FORWARD requires a 'backtest_results' artifact.")

        elif target == LifecycleStage.PAPER_TRADING:
            if "walk_forward_results" not in request.artifacts:
                raise ValueError("Promotion to PAPER_TRADING requires a 'walk_forward_results' artifact.")

        elif target == LifecycleStage.RISK_REVIEW:
            if "paper_trading_results" not in request.artifacts:
                raise ValueError("Promotion to RISK_REVIEW requires a 'paper_trading_results' artifact.")

        elif target == LifecycleStage.AI_REVIEW:
            # Requires RISK approval
            risk_approved = any(a.reviewer_type == "RISK" and a.approved for a in approvals)
            if not risk_approved:
                raise ValueError("Promotion to AI_REVIEW requires an approved RISK review record.")

        elif target == LifecycleStage.HUMAN_APPROVAL:
            # Requires AI approval
            ai_approved = any(a.reviewer_type == "AI" and a.approved for a in approvals)
            if not ai_approved:
                raise ValueError("Promotion to HUMAN_APPROVAL requires an approved AI review record.")

        elif target == LifecycleStage.READY_FOR_DEPLOYMENT:
            # Requires HUMAN approval
            human_approved = any(a.reviewer_type == "HUMAN" and a.approved for a in approvals)
            if not human_approved:
                raise ValueError("Promotion to READY_FOR_DEPLOYMENT requires an approved HUMAN review record.")

        elif target == LifecycleStage.CANARY:
            pass

        elif target == LifecycleStage.LIVE:
            # Requires Canary success evidence
            if "canary_passed" not in request.artifacts or not request.artifacts["canary_passed"]:
                raise ValueError("Promotion to LIVE requires a 'canary_passed' verification artifact.")

        return True
