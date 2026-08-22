"""Risk Engine analysis implementation coordinating all risk validators."""

from __future__ import annotations

import logging
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.interfaces import IRiskEngine, IRiskValidator
from risk_engine.core.models import RiskFactor, RiskAssessment
from risk_engine.analysis.validators import (
    DailyLossValidator,
    DrawdownValidator,
    VolatilityValidator,
    CorrelationValidator,
    SessionValidator,
    LiquidityValidator,
    NewsValidator,
    WeekendValidator,
    ConflictValidator,
)

logger = logging.getLogger(__name__)


class RiskEngine(IRiskEngine):
    """Executes all validators sequentially, aggregates penalties, and assigns a risk decision."""

    def __init__(self) -> None:
        self._validators: list[IRiskValidator] = [
            DailyLossValidator(),
            DrawdownValidator(),
            VolatilityValidator(),
            CorrelationValidator(),
            SessionValidator(),
            LiquidityValidator(),
            NewsValidator(),
            WeekendValidator(),
            ConflictValidator(),
        ]

    def evaluate(self, context: TradingContext, **kwargs: Any) -> RiskAssessment:
        """Run all registered validators against the current context and return a RiskAssessment."""
        factors: list[RiskFactor] = []
        violations: list[str] = []
        total_penalty = 0.0
        has_critical = False
        has_high = False

        for validator in self._validators:
            try:
                factor, penalty, reason = validator.validate(context, **kwargs)
                if factor is not None:
                    factors.append(factor)
                    total_penalty += penalty
                    if reason:
                        violations.append(reason)

                    if factor.severity == RiskSeverity.CRITICAL:
                        has_critical = True
                    elif factor.severity == RiskSeverity.HIGH:
                        has_high = True
            except Exception as e:
                logger.error("RiskEngine: Validator execution failed: %s", e)
                # We fail-safe: any validator crash adds a HIGH penalty of 25 to protect capital
                fail_safe_factor = RiskFactor(
                    id="RE_FAILSAFE_001",
                    name="Validator Execution Crash",
                    severity=RiskSeverity.HIGH,
                    score=25.0,
                    description=f"Validator failed to run due to exception: {e}",
                )
                factors.append(fail_safe_factor)
                total_penalty += 25.0
                violations.append(f"Validator crash: {e}")
                has_high = True

        # Clamp overall score between 0.0 and 100.0
        overall_score = max(0.0, min(100.0, 100.0 - total_penalty))

        # Decision routing logic
        if overall_score < 80.0 or has_critical:
            decision = RiskDecision.BLOCK
        elif (80.0 <= overall_score < 85.0) or has_high:
            decision = RiskDecision.REVIEW
        else:
            decision = RiskDecision.ALLOW

        return RiskAssessment(
            overall_score=round(overall_score, 2),
            decision=decision,
            factors=factors,
            violations=violations,
        )

    def evaluate_execution_request(self, request: Any, **kwargs: Any) -> RiskAssessment:
        """Evaluate an execution request against all risk check rules before broker routing."""
        from risk_engine.analysis.rules_engine import RiskRulesEngine
        from risk_engine.core.models import (
            AccountRisk,
            PortfolioRisk,
            ExposureRisk,
            DrawdownRisk,
            MarginRisk,
            LeverageRisk,
            CircuitBreakerState,
            RiskMetrics,
            RiskConfiguration,
        )

        # --- Fail-Closed Attribute Validation (RE_PAYLOAD_001) ---
        # Required: symbol, quantity, price. Missing or invalid → fail closed immediately.
        symbol = getattr(request, "symbol", None)
        timeframe = getattr(request, "timeframe", None)
        raw_qty = getattr(request, "quantity", None)
        raw_price = getattr(request, "price", None)
        # Allow price override from kwargs only when request.price is explicitly provided and valid.
        if raw_price is None:
            raw_price = kwargs.get("entry_price", None)

        missing_fields = []
        if not symbol or not str(symbol).strip():
            missing_fields.append("symbol")
        if raw_qty is None or float(raw_qty) <= 0:
            missing_fields.append("quantity (must be > 0)")
        if raw_price is None or float(raw_price) <= 0:
            missing_fields.append("price (must be > 0)")

        if missing_fields:
            raise ValueError(
                f"RiskEngine.evaluate_execution_request: RE_PAYLOAD_001 — "
                f"missing or invalid required field(s): {', '.join(missing_fields)}. "
                "No risk evaluation performed on fabricated inputs."
            )

        symbol = str(symbol)
        timeframe = str(timeframe) if timeframe else "UNKNOWN"
        qty = float(raw_qty)
        price = float(raw_price)
        leverage = float(getattr(request, "leverage", 1.0))
        margin_required = float(getattr(request, "margin_required", 0.0))

        account_risk = kwargs.get("account_risk", AccountRisk())
        portfolio_risk = kwargs.get("portfolio_risk", PortfolioRisk())
        exposure_risk = kwargs.get("exposure_risk", ExposureRisk())
        drawdown_risk = kwargs.get("drawdown_risk", DrawdownRisk())
        margin_risk = kwargs.get("margin_risk", MarginRisk())
        leverage_risk = kwargs.get("leverage_risk", LeverageRisk())
        circuit_breaker = kwargs.get("circuit_breaker", CircuitBreakerState(halt_trading=False))
        metrics = kwargs.get("metrics", RiskMetrics())
        config = kwargs.get("config", RiskConfiguration())

        rules_engine = RiskRulesEngine()
        risk_state = rules_engine.evaluate_request(
            symbol=symbol,
            timeframe=timeframe,
            quantity=qty,
            price=price,
            leverage=leverage,
            margin_required=margin_required,
            account_risk=account_risk,
            portfolio_risk=portfolio_risk,
            exposure_risk=exposure_risk,
            drawdown_risk=drawdown_risk,
            margin_risk=margin_risk,
            leverage_risk=leverage_risk,
            circuit_breaker=circuit_breaker,
            metrics=metrics,
            config=config,
            **kwargs,
        )
        return risk_state.assessment
