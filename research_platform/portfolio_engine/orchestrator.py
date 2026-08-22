"""Portfolio Engine Orchestrator coordinating returns forecasting, covariance steps, MVO, and risk budgets.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.portfolio_engine.allocator import PortfolioAllocator
from research_platform.portfolio_engine.constraints import ConstraintEngine
from research_platform.portfolio_engine.covariance import CovarianceEngine
from research_platform.portfolio_engine.events import (
    AllocationCompleted,
    PortfolioCreated,
    PortfolioOptimized,
    PortfolioUpdated,
    RiskCalculated
)
from research_platform.portfolio_engine.factor_model import FactorModel
from research_platform.portfolio_engine.forecast import ForecastEngine
from research_platform.portfolio_engine.models import (
    AllocationResult,
    Portfolio,
    PortfolioConfiguration,
    PortfolioLifecycle,
    PortfolioMetadata,
    PortfolioSnapshot,
    PortfolioVersion,
    PortfolioWeights
)
from research_platform.portfolio_engine.optimizer import PortfolioOptimizer
from research_platform.portfolio_engine.performance import BrinsonAttribution
from research_platform.portfolio_engine.rebalancer import PortfolioRebalancer
from research_platform.portfolio_engine.repository import PortfolioRepository
from research_platform.portfolio_engine.risk_budget import PortfolioRiskBudget

logger = logging.getLogger(__name__)


class PortfolioEngineOrchestrator:
    """Coordinates the portfolio forecast -> covariance -> optimization -> attribution pipeline."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = PortfolioRepository()
        self._forecaster = ForecastEngine()
        self._covariance = CovarianceEngine()
        self._risk = PortfolioRiskBudget()
        self._constraints = ConstraintEngine()
        self._performance = BrinsonAttribution()

    @property
    def repository(self) -> PortfolioRepository:
        return self._repo

    def construct_portfolio(
        self,
        config: PortfolioConfiguration,
        price_df: pd.DataFrame
    ) -> PortfolioWeights:
        """Execute the returns forecasting, covariance estimation, and optimization sequence.

        Returns:
            Calculated target portfolio weights.
        """
        symbols = list(price_df.columns)
        returns_df = price_df.pct_change().dropna()

        # 1. Forecast expected returns
        forecast = self._forecaster.forecast_returns(price_df)

        # 2. Estimate returns covariance
        cov = self._covariance.calculate_covariance(returns_df)

        # 3. MVO/Risk Parity optimization
        opt = PortfolioOptimizer(optimizer_name=config.optimizer_type.lower())
        opt_res = opt.optimize(symbols, forecast, cov)
        self._event_bus.publish(PortfolioOptimized(payload={"portfolio_id": config.portfolio_id}))

        # 4. Enforce constraints
        violations = self._constraints.check_constraints(opt_res.weights)
        for v in violations:
            logger.warning("Constraint violation during construction: %s", v.details)

        # 5. Evaluate risk budget
        rc = self._risk.calculate_risk_contributions(opt_res.weights, cov)
        self._event_bus.publish(RiskCalculated(payload={"portfolio_id": config.portfolio_id}))

        # 6. High level catalog registration
        port = Portfolio(
            portfolio_id=config.portfolio_id,
            name=f"Portfolio_{config.portfolio_id[:8]}",
            display_name=f"Portfolio {config.portfolio_id}",
            description="Institutional allocation",
            version=PortfolioVersion(version_num="1.0", changelog="Initial construction"),
            lifecycle=PortfolioLifecycle(effective_time=datetime.now(timezone.utc)),
            metadata=PortfolioMetadata(author="CTO")
        )
        self._repo.save_portfolio(port)
        self._event_bus.publish(PortfolioCreated(payload={"portfolio_id": config.portfolio_id}))

        # 7. Save allocation weights
        alloc = AllocationResult(
            allocator_name=config.optimizer_type,
            weights=opt_res.weights,
            total_allocated=sum(opt_res.weights.weights.values())
        )
        self._repo.save_allocation(config.portfolio_id, alloc)
        self._event_bus.publish(AllocationCompleted(payload={"portfolio_id": config.portfolio_id}))

        return opt_res.weights
