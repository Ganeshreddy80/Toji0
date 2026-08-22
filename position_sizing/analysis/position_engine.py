"""Unified Position Sizing Engine coordinating calculators and validations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from risk_engine.core.enums import RiskDecision
from position_sizing.core.enums import SizingStatus, PositionSizingMethod
from position_sizing.core.interfaces import IPositionSizingEngine
from position_sizing.core.models import PositionSize, PositionSizingResult
from position_sizing.analysis.sizing_selector import SizingSelector
from position_sizing.analysis.leverage_calculator import LeverageCalculator
from position_sizing.analysis.margin_calculator import MarginCalculator
from position_sizing.analysis.exposure_validator import ExposureValidator

logger = logging.getLogger(__name__)


class PositionSizingEngine(IPositionSizingEngine):
    """Unified engine to select, compute, and validate position sizes."""

    def __init__(self) -> None:
        self._selector = SizingSelector()
        self._leverage_calc = LeverageCalculator()
        self._margin_calc = MarginCalculator()
        self._validator = ExposureValidator()

    def calculate_size(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> PositionSizingResult:
        """Calculate position sizing based on context, risk assessments, and configs."""
        timestamp = datetime.now(timezone.utc)

        # 1. Immediate rejection if risk is blocked
        if risk_assessment.decision == RiskDecision.BLOCK:
            logger.warning("PositionSizingEngine: Short-circuiting pipeline due to BLOCK risk decision.")
            violations_str = [
                v.message if hasattr(v, "message") else str(v)
                for v in risk_assessment.violations
            ] if risk_assessment.violations else ["Risk check failed."]
            reasons_str = [
                f"Risk assessment rejected the trade proposal: {v}" for v in violations_str
            ]
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=reasons_str,
                violations=violations_str,
                timestamp=timestamp,
            )

        # 2. Extract configuration params
        balance = float(kwargs.get("account_balance", kwargs.get("balance", 0.0)))
        entry_price = float(kwargs.get("entry_price", 0.0))
        max_leverage_limit = float(kwargs.get("max_leverage", 10.0))
        contract_size = float(kwargs.get("contract_size", 1.0))
        method_name = kwargs.get("default_sizing_method", PositionSizingMethod.FIXED_FRACTIONAL)

        if balance <= 0:
            logger.warning("PositionSizingEngine: Rejected sizing calculation due to invalid account balance: %s", balance)
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=["Account balance must be positive."],
                violations=["Invalid account balance."],
                timestamp=timestamp,
            )

        if entry_price <= 0:
            logger.warning("PositionSizingEngine: Rejected sizing calculation due to invalid entry price: %s", entry_price)
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=["Entry price must be positive."],
                violations=["Invalid entry price."],
                timestamp=timestamp,
            )

        # Determine stop distance — NEVER fabricate fallback values
        stop_distance: float | None = None
        raw_stop_dist = kwargs.get("stop_distance")
        if raw_stop_dist is not None:
            stop_distance = float(raw_stop_dist)
        else:
            raw_stop_loss = kwargs.get("stop_loss")
            if raw_stop_loss is not None:
                sl_val = float(raw_stop_loss)
                if sl_val > 0 and sl_val != entry_price:
                    stop_distance = abs(entry_price - sl_val)

        if stop_distance is None or stop_distance <= 0:
            logger.warning(
                "PositionSizingEngine: Rejected sizing calculation due to missing or invalid stop-loss parameter "
                "(stop_distance=%s, stop_loss=%s).",
                kwargs.get("stop_distance"),
                kwargs.get("stop_loss"),
            )
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=["Missing or invalid stop-loss parameters."],
                violations=["Required parameter 'stop_loss' or 'stop_distance' must be provided and positive."],
                timestamp=timestamp,
            )

        # Determine take profit distance — NEVER fabricate fallback values
        take_profit_distance: float | None = None
        raw_tp_dist = kwargs.get("take_profit_distance")
        if raw_tp_dist is not None:
            take_profit_distance = float(raw_tp_dist)
        else:
            raw_take_profit = kwargs.get("take_profit")
            if raw_take_profit is not None:
                tp_val = float(raw_take_profit)
                if tp_val > 0 and tp_val != entry_price:
                    take_profit_distance = abs(tp_val - entry_price)

        if take_profit_distance is None or take_profit_distance <= 0:
            logger.warning(
                "PositionSizingEngine: Rejected sizing calculation due to missing or invalid take-profit parameter "
                "(take_profit_distance=%s, take_profit=%s).",
                kwargs.get("take_profit_distance"),
                kwargs.get("take_profit"),
            )
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=["Missing or invalid take-profit parameters."],
                violations=["Required parameter 'take_profit' or 'take_profit_distance' must be provided and positive."],
                timestamp=timestamp,
            )

        # 3. Resolve sizing calculator and compute quantity
        try:
            calculator = self._selector.select_calculator(method_name, **kwargs)
            quantity, reasons = calculator.calculate(context, risk_assessment, **kwargs)
        except ValueError as exc:
            logger.error(
                "PositionSizingEngine: Invalid sizing configuration: %s",
                exc,
            )
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=[f"Invalid sizing configuration: {exc}"],
                violations=[str(exc)],
                timestamp=timestamp,
            )
        except Exception as exc:
            logger.error(
                "PositionSizingEngine: Unexpected error during sizing calculation: %s",
                exc,
                exc_info=True,
            )
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=["Sizing calculation failed due to an unexpected error."],
                violations=[f"Internal error: {exc}"],
                timestamp=timestamp,
            )

        if quantity <= 0:
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=reasons,
                violations=["Computed quantity must be greater than zero."],
                timestamp=timestamp,
            )

        # 4. Clean kwargs to avoid duplicate keyword arguments
        clean_kwargs = dict(kwargs)
        for key in ["quantity", "entry_price", "account_balance", "balance", "max_leverage", "max_leverage_limit", "leverage", "stop_distance", "required_leverage", "required_margin", "max_single_trade_risk_pct", "max_portfolio_exposure_pct"]:
            clean_kwargs.pop(key, None)

        # Calculate leverage metrics
        leverage_details = self._leverage_calc.calculate_leverage(
            quantity=quantity,
            entry_price=entry_price,
            balance=balance,
            max_leverage_limit=max_leverage_limit,
            **clean_kwargs,
        )
        required_leverage = leverage_details["required_leverage"]

        # 5. Calculate margin metrics
        margin_details = self._margin_calc.calculate_margin(
            quantity=quantity,
            entry_price=entry_price,
            leverage=required_leverage,
            balance=balance,
            **clean_kwargs,
        )
        required_margin = margin_details["required_margin"]

        # 6. Run exposure validations
        max_single_trade_risk_pct = float(kwargs.get("max_single_trade_risk_pct", 0.02))
        max_portfolio_exposure_pct = float(kwargs.get("max_portfolio_exposure_pct", 0.50))
        
        valid, violations = self._validator.validate(
            quantity=quantity,
            entry_price=entry_price,
            balance=balance,
            stop_distance=stop_distance,
            required_leverage=required_leverage,
            required_margin=required_margin,
            max_leverage_limit=max_leverage_limit,
            max_single_trade_risk_pct=max_single_trade_risk_pct,
            max_portfolio_exposure_pct=max_portfolio_exposure_pct,
            **clean_kwargs,
        )

        if not valid:
            logger.info("PositionSizingEngine: Exposure validation failed: %s", violations)
            return PositionSizingResult(
                success=False,
                status=SizingStatus.REJECTED,
                position_size=None,
                reasons=reasons,
                violations=violations,
                timestamp=timestamp,
            )

        # 7. Build successful PositionSize object
        lots = quantity / contract_size
        capital_used = quantity * entry_price
        account_risk_percent = (quantity * stop_distance) / balance

        # Resolve sizing method enum
        if isinstance(method_name, str):
            method_enum = PositionSizingMethod[method_name.upper()]
        else:
            method_enum = method_name

        # Sizing confidence can be adjusted based on confluence or default to 1.0
        confidence = 1.0
        if context.confluence_state and context.confluence_state.score:
            confidence = float(context.confluence_state.score.overall_score) / 100.0

        expected_loss = quantity * stop_distance
        expected_gain = quantity * take_profit_distance
        reason_str = reasons[-1] if reasons else "Approved sizing calculation."

        position_size = PositionSize(
            symbol=context.symbol,
            timeframe=context.timeframe,
            quantity=quantity,
            lots=lots,
            leverage=required_leverage,
            margin_required=required_margin,
            account_risk_percent=account_risk_percent,
            capital_used=capital_used,
            stop_distance=stop_distance,
            take_profit_distance=take_profit_distance,
            sizing_method=method_enum,
            confidence=confidence,
            expected_loss=expected_loss,
            expected_gain=expected_gain,
            reason=reason_str,
            timestamp=timestamp,
        )

        return PositionSizingResult(
            success=True,
            status=SizingStatus.APPROVED,
            position_size=position_size,
            reasons=reasons + [f"Position sized approved: quantity={quantity:.4f}, leverage={required_leverage:.2f}."],
            violations=[],
            timestamp=timestamp,
        )
