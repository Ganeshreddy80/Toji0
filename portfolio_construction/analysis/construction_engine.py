"""Authoritative Portfolio Construction Engine implementation."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from typing import Dict, List, Optional

from portfolio_construction.core.enums import OptimizationObjective, PortfolioDecision
from portfolio_construction.core.interfaces import (
    ICorrelationFilter,
    IDiversificationEngine,
    IPortfolioConstraintEngine,
    IPortfolioConstructionEngine,
    IPortfolioOptimizer,
)
from portfolio_construction.core.models import (
    PortfolioCandidate,
    PortfolioConstraintConfig,
    TargetAllocation,
    TargetPortfolio,
)
from portfolio_construction.analysis.constraint_engine import PortfolioConstraintEngine
from portfolio_construction.analysis.correlation_filter import CorrelationFilter
from portfolio_construction.analysis.diversification_engine import DiversificationEngine
from portfolio_construction.analysis.optimizer import PortfolioOptimizer

logger = logging.getLogger(__name__)


class PortfolioConstructionEngine(IPortfolioConstructionEngine):
    """Authoritative engine converting strategy candidates into an institutional target portfolio."""

    def __init__(
        self,
        correlation_filter: Optional[ICorrelationFilter] = None,
        diversification_engine: Optional[IDiversificationEngine] = None,
        constraint_engine: Optional[IPortfolioConstraintEngine] = None,
        optimizer: Optional[IPortfolioOptimizer] = None,
    ) -> None:
        self._correlation_filter = correlation_filter or CorrelationFilter()
        self._diversification_engine = diversification_engine or DiversificationEngine()
        self._constraint_engine = constraint_engine or PortfolioConstraintEngine()
        self._optimizer = optimizer or PortfolioOptimizer()

    def construct_portfolio(
        self,
        candidates: List[PortfolioCandidate],
        correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        config: Optional[PortfolioConstraintConfig] = None,
        objective: OptimizationObjective = OptimizationObjective.CONFIDENCE_WEIGHTED,
    ) -> TargetPortfolio:
        """
        Construct an institutional target portfolio from strategy setup candidates.
        Fails closed to a HOLD posture if inputs are missing, corrupted, or violate constraints.
        """
        config = config or PortfolioConstraintConfig()
        matrix = correlation_matrix or {}

        # 1. Fail-Closed Guard: Validate input candidate set
        if not candidates:
            logger.info("PortfolioConstructionEngine: Candidate set is empty. Returning HOLD posture.")
            return TargetPortfolio(
                portfolio_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                decision=PortfolioDecision.HOLD,
                allocations={},
                target_weights={},
                total_weight=0.0,
                active_positions_count=0,
                confidence=0.0,
                reasoning="Fail-Closed: Candidate set is empty. Maintain HOLD posture.",
                rejected_candidates=[],
            )

        all_rejected: List[str] = []

        try:
            # 2. Correlation Filtering
            corr_candidates, corr_rejected = self._correlation_filter.filter_candidates(
                candidates=candidates,
                correlation_matrix=matrix,
                max_correlation=config.max_correlation,
            )
            all_rejected.extend(corr_rejected)

            if not corr_candidates:
                logger.warning("PortfolioConstructionEngine: All candidates rejected by correlation filter.")
                return TargetPortfolio(
                    portfolio_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    decision=PortfolioDecision.HOLD,
                    allocations={},
                    target_weights={},
                    total_weight=0.0,
                    active_positions_count=0,
                    confidence=0.0,
                    reasoning="Fail-Closed: All candidates rejected by correlation filter.",
                    rejected_candidates=all_rejected,
                )

            # 3. Diversification Engine (Max positions & Sector caps)
            div_candidates, div_rejected = self._diversification_engine.apply_diversification(
                candidates=corr_candidates,
                config=config,
            )
            all_rejected.extend(div_rejected)

            if not div_candidates:
                logger.warning("PortfolioConstructionEngine: All candidates rejected by diversification limits.")
                return TargetPortfolio(
                    portfolio_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    decision=PortfolioDecision.HOLD,
                    allocations={},
                    target_weights={},
                    total_weight=0.0,
                    active_positions_count=0,
                    confidence=0.0,
                    reasoning="Fail-Closed: All candidates rejected by diversification limits.",
                    rejected_candidates=all_rejected,
                )

            # 4. Portfolio Optimization (Target Weight Allocation)
            target_weights = self._optimizer.optimize(
                candidates=div_candidates,
                correlation_matrix=matrix,
                config=config,
                objective=objective,
            )

            if not target_weights:
                logger.warning("PortfolioConstructionEngine: Optimizer returned empty weight allocation.")
                return TargetPortfolio(
                    portfolio_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    decision=PortfolioDecision.HOLD,
                    allocations={},
                    target_weights={},
                    total_weight=0.0,
                    active_positions_count=0,
                    confidence=0.0,
                    reasoning="Fail-Closed: Optimizer produced empty weight allocation.",
                    rejected_candidates=all_rejected,
                )

            # 5. Final Constraint Engine Validation
            is_valid, violations = self._constraint_engine.validate_constraints(
                candidates=div_candidates,
                weights=target_weights,
                config=config,
            )

            if not is_valid:
                logger.error("PortfolioConstructionEngine: Target portfolio failed constraint validation: %s. Failing closed to HOLD.", violations)
                return TargetPortfolio(
                    portfolio_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    decision=PortfolioDecision.HOLD,
                    allocations={},
                    target_weights={},
                    total_weight=0.0,
                    active_positions_count=0,
                    confidence=0.0,
                    reasoning=f"Fail-Closed: Constraint violations: {'; '.join(violations)}",
                    rejected_candidates=all_rejected + list(target_weights.keys()),
                )

            # Build final approved target allocations
            candidate_map = {c.symbol: c for c in div_candidates}
            allocations: Dict[str, TargetAllocation] = {}

            for sym, w in target_weights.items():
                cand = candidate_map[sym]
                allocations[sym] = TargetAllocation(
                    symbol=sym,
                    target_weight=round(w, 4),
                    confidence=cand.confidence,
                    strategy_type=cand.strategy_type,
                    reasoning=f"Allocated target weight {w:.4f} via {objective.value} optimization.",
                )

            total_w = round(sum(target_weights.values()), 4)
            avg_conf = round(sum(c.confidence for c in div_candidates) / len(div_candidates), 4)

            decision = PortfolioDecision.REBALANCE if total_w > 0.0 else PortfolioDecision.HOLD

            return TargetPortfolio(
                portfolio_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                decision=decision,
                allocations=allocations,
                target_weights=target_weights,
                total_weight=total_w,
                active_positions_count=len(allocations),
                confidence=avg_conf,
                reasoning=f"Successfully constructed {decision.value} portfolio across {len(allocations)} assets with total weight {total_w:.4f}.",
                rejected_candidates=all_rejected,
            )

        except Exception as e:
            logger.error("PortfolioConstructionEngine: Unexpected failure during construction: %s. Failing closed.", e, exc_info=True)
            return TargetPortfolio(
                portfolio_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                decision=PortfolioDecision.HOLD,
                allocations={},
                target_weights={},
                total_weight=0.0,
                active_positions_count=0,
                confidence=0.0,
                reasoning=f"Fail-Closed: Construction engine error: {e}",
                rejected_candidates=all_rejected,
            )
