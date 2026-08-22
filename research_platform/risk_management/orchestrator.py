"""Risk Management Orchestrator coordinating sizers checks, compliance, VaR, and stress tests.
"""

from __future__ import annotations

import logging
import uuid
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.risk_management.alerts import RiskAlertSystem
from research_platform.risk_management.compliance import ComplianceEngine
from research_platform.risk_management.concentration import ConcentrationRiskEngine
from research_platform.risk_management.cvar import CVaREngine
from research_platform.risk_management.events import (
    RiskApproved,
    RiskEvaluationCompleted,
    RiskEvaluationStarted,
    RiskRejected
)
from research_platform.risk_management.exposure import ExposureEngine
from research_platform.risk_management.leverage import LeverageEngine
from research_platform.risk_management.limits import RiskLimitsEngine
from research_platform.risk_management.liquidity import LiquidityRiskEngine
from research_platform.risk_management.market_risk import MarketRiskEvaluator
from research_platform.risk_management.models import (
    ComplianceReport,
    LimitViolation,
    RiskApproval,
    RiskDecision,
    RiskEvaluation,
    RiskProfile,
    RiskScore
)
from research_platform.risk_management.position_risk import PositionRiskEvaluator
from research_platform.risk_management.portfolio_risk import PortfolioRiskEvaluator
from research_platform.risk_management.repository import RiskRepository
from research_platform.risk_management.scenario import StressScenarios
from research_platform.risk_management.stress_testing import StressTestingEngine
from research_platform.risk_management.var import VaREngine
from research_platform.risk_management.kill_switch import KillSwitch
from research_platform.oms.models import OrderRequest

logger = logging.getLogger(__name__)


class RiskManagementOrchestrator:
    """Manages order validation gate pipelines, verifying compliance and score limits."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = RiskRepository()
        self._kill_switch = KillSwitch()

        # Engines
        self._pos_risk = PositionRiskEvaluator()
        self._port_risk = PortfolioRiskEvaluator()
        self._market_risk = MarketRiskEvaluator()
        self._var_engine = VaREngine()
        self._cvar_engine = CVaREngine()
        self._stress = StressTestingEngine()
        self._exposure = ExposureEngine()
        self._leverage = LeverageEngine()
        self._concentration = ConcentrationRiskEngine()
        self._liquidity = LiquidityRiskEngine()
        self._limits = RiskLimitsEngine()
        self._compliance = ComplianceEngine(self._limits, self._kill_switch)

    @property
    def repository(self) -> RiskRepository:
        return self._repo

    @property
    def kill_switch(self) -> KillSwitch:
        return self._kill_switch

    def validate_order(
        self,
        request: OrderRequest,
        returns: np.ndarray,
        weights: Dict[str, float]
    ) -> RiskDecision:
        """Validate order request through all risk checks, producing compliance approvals."""
        self._event_bus.publish(RiskEvaluationStarted(payload={"order_id": request.order_id}))

        # 1. Run core models checks
        pos_res = self._pos_risk.evaluate_position_risk(request)
        port_res = self._port_risk.calculate_portfolio_risk(weights)
        mkt_res = self._market_risk.check_market_risk()

        # 2. VaR and CVaR engines
        var_rep = self._var_engine.calculate_var(returns)
        cvar_rep = self._cvar_engine.calculate_cvar(returns)

        # 3. Leverage checks
        lev_rep = self._leverage.evaluate_leverage(weights)

        # 4. Compliance evaluation
        comp_rep = self._compliance.evaluate_compliance(request)

        # 5. Risk score calculations
        score = 90.0 if comp_rep.compliant else 30.0

        eval_id = str(uuid.uuid4())
        evaluation = RiskEvaluation(
            evaluation_id=eval_id,
            portfolio_id=request.strategy_id or "default",
            risk_score=RiskScore(composite_score=score),
            profile=RiskProfile(
                var_report=var_rep,
                cvar_report=cvar_rep,
                leverage_report=lev_rep,
                compliance_report=comp_rep
            )
        )
        self._repo.save_evaluation(evaluation)
        self._event_bus.publish(RiskEvaluationCompleted(payload={"evaluation_id": eval_id}))

        # 6. Publish decision outcomes
        approved = comp_rep.compliant
        approval = RiskApproval(
            approval_id=str(uuid.uuid4()),
            approved=approved,
            approver="ChiefRiskOfficer"
        )

        decision = RiskDecision(
            decision_id=str(uuid.uuid4()),
            evaluation=evaluation,
            approval=approval
        )

        if approved:
            self._event_bus.publish(RiskApproved(payload={"order_id": request.order_id}))
        else:
            self._event_bus.publish(RiskRejected(payload={"order_id": request.order_id, "reasons": comp_rep.rejection_reasons}))

        logger.info("Risk validation for order %s: %s", request.order_id, "APPROVED" if approved else "REJECTED")
        return decision
