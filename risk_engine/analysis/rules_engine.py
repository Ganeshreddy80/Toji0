"""Modular Risk Rules Engine executing the 28 risk validation rules."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.models import (
    RiskFactor,
    RiskViolation,
    RiskAssessment,
    RiskConfiguration,
    AccountRisk,
    PortfolioRisk,
    ExposureRisk,
    DrawdownRisk,
    MarginRisk,
    LeverageRisk,
    CircuitBreakerState,
    RiskMetrics,
    RiskState,
)

logger = logging.getLogger(__name__)


class RiskRulesEngine:
    """Evaluates all 28 institutional risk rules against context or execution requests."""

    def __init__(self) -> None:
        pass

    def evaluate_request(
        self,
        symbol: str,
        timeframe: str,
        quantity: float,
        price: float,
        leverage: float,
        margin_required: float,
        account_risk: AccountRisk,
        portfolio_risk: PortfolioRisk,
        exposure_risk: ExposureRisk,
        drawdown_risk: DrawdownRisk,
        margin_risk: MarginRisk,
        leverage_risk: LeverageRisk,
        circuit_breaker: CircuitBreakerState,
        metrics: RiskMetrics,
        config: RiskConfiguration,
        **kwargs: Any,
    ) -> RiskState:
        """
        Evaluate all risk rules for a specific execution request or context change.
        """
        factors: list[RiskFactor] = []
        violations: list[RiskViolation] = []
        total_penalty = 0.0

        # Master Override Bypass
        if config.risk_override:
            logger.warning("RiskRulesEngine: RISK OVERRIDE active. Bypassing all rules.")
            assessment = RiskAssessment(
                overall_score=100.0,
                decision=RiskDecision.ALLOW,
                factors=[
                    RiskFactor(
                        id="RE_OVERRIDE_001",
                        name="Risk Override Active",
                        severity=RiskSeverity.LOW,
                        score=0.0,
                        description="All risk limits bypassed via configuration override.",
                    )
                ],
                violations=[],
            )
            return RiskState(
                symbol=symbol,
                timeframe=timeframe,
                assessment=assessment,
                account_risk=account_risk,
                portfolio_risk=portfolio_risk,
                exposure_risk=exposure_risk,
                drawdown_risk=drawdown_risk,
                margin_risk=margin_risk,
                leverage_risk=leverage_risk,
                circuit_breaker=circuit_breaker,
                metrics=metrics,
                config=config,
            )

        # 1. Manual Kill Switch
        if config.manual_kill_switch:
            self._add_violation("RE_KIL_001", "Manual Kill Switch", "Manual kill switch has been activated.", RiskSeverity.CRITICAL, 100.0, factors, violations)

        # 2. Emergency Stop
        if config.emergency_stop:
            self._add_violation("RE_EST_001", "Emergency Stop", "Emergency stop has been triggered.", RiskSeverity.CRITICAL, 100.0, factors, violations)

        # 3. Cooldown Period / Circuit Breaker Halt
        if circuit_breaker.halt_trading:
            self._add_violation("RE_COOLDOWN", "Trading Cooldown Active", "System trading is halted due to active circuit breakers or cooldown.", RiskSeverity.CRITICAL, 100.0, factors, violations)

        # 4. Market Halt
        if config.market_halt:
            self._add_violation("RE_MHALT", "Market Halt Active", "Market trading is explicitly halted.", RiskSeverity.CRITICAL, 100.0, factors, violations)

        # 5. Exchange Maintenance
        if config.exchange_maintenance:
            self._add_violation("RE_MAINT", "Exchange Maintenance", "Exchange is currently undergoing maintenance.", RiskSeverity.CRITICAL, 100.0, factors, violations)

        # Account Balance Integrity Check (Fail-closed if account uninitialized or balance non-positive)
        if account_risk.initial_balance <= 0 or account_risk.equity <= 0:
            logger.critical(
                "RE_ACC_001: Uninitialized or invalid account state detected — "
                "equity=$%.2f initial_balance=$%.2f. Blocking trade immediately.",
                account_risk.equity,
                account_risk.initial_balance,
            )
            self._add_violation(
                "RE_ACC_001",
                "Uninitialized or Invalid Account State",
                f"Account equity (${account_risk.equity:,.2f}) or initial balance (${account_risk.initial_balance:,.2f}) is non-positive or uninitialized.",
                RiskSeverity.CRITICAL,
                100.0,
                factors,
                violations,
            )

        # 6. Maximum Daily Loss
        daily_loss_pct = 0.0
        if account_risk.initial_balance > 0:
            daily_loss_pct = (account_risk.initial_balance - account_risk.equity) / account_risk.initial_balance
        if daily_loss_pct >= config.daily_loss_limit:
            self._add_violation(
                "RE_MDL_001",
                "Daily Loss Limit Exceeded",
                f"Daily loss pct {daily_loss_pct*100:.2f}% >= limit {config.daily_loss_limit*100:.2f}%.",
                RiskSeverity.CRITICAL,
                100.0,
                factors,
                violations,
            )

        # 7. Maximum Weekly Loss
        # In mock tests or environment we can pass weekly/monthly PnL pct via kwargs
        weekly_loss_pct = float(kwargs.get("weekly_loss_pct", daily_loss_pct))
        if weekly_loss_pct >= config.weekly_loss_limit:
            self._add_violation(
                "RE_MWL_001",
                "Weekly Loss Limit Exceeded",
                f"Weekly loss pct {weekly_loss_pct*100:.2f}% >= limit {config.weekly_loss_limit*100:.2f}%.",
                RiskSeverity.CRITICAL,
                100.0,
                factors,
                violations,
            )

        # 8. Maximum Monthly Loss
        monthly_loss_pct = float(kwargs.get("monthly_loss_pct", daily_loss_pct))
        if monthly_loss_pct >= config.monthly_loss_limit:
            self._add_violation(
                "RE_MML_001",
                "Monthly Loss Limit Exceeded",
                f"Monthly loss pct {monthly_loss_pct*100:.2f}% >= limit {config.monthly_loss_limit*100:.2f}%.",
                RiskSeverity.CRITICAL,
                100.0,
                factors,
                violations,
            )

        # 9. Maximum Drawdown
        if drawdown_risk.rolling_drawdown >= config.max_drawdown_limit:
            self._add_violation(
                "RE_MDD_001",
                "Maximum Drawdown Limit Exceeded",
                f"Current drawdown {drawdown_risk.rolling_drawdown*100:.2f}% >= limit {config.max_drawdown_limit*100:.2f}%.",
                RiskSeverity.CRITICAL,
                100.0,
                factors,
                violations,
            )

        # 10. Maximum Consecutive Losses
        consecutive_losses = int(kwargs.get("consecutive_losses", 0))
        if consecutive_losses >= config.max_consecutive_losses:
            self._add_violation(
                "RE_MCL_001",
                "Maximum Consecutive Losses Breached",
                f"Consecutive losses count {consecutive_losses} >= limit {config.max_consecutive_losses}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 11. Maximum Losing Streak
        losing_streak = int(kwargs.get("losing_streak", consecutive_losses))
        if losing_streak >= config.max_losing_streak:
            self._add_violation(
                "RE_MLS_001",
                "Maximum Losing Streak Breached",
                f"Losing streak length {losing_streak} >= limit {config.max_losing_streak}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 12. Maximum Open Positions
        if portfolio_risk.open_positions_count >= config.max_open_positions:
            self._add_violation(
                "RE_MOP_001",
                "Maximum Open Positions Breached",
                f"Open positions count {portfolio_risk.open_positions_count} >= limit {config.max_open_positions}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 13. Maximum Position Size
        req_val = quantity * price
        if req_val > config.max_position_size:
            self._add_violation(
                "RE_MPS_001",
                "Maximum Position Size Breached",
                f"Requested position value ${req_val:,.2f} > limit ${config.max_position_size:,.2f}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 14. Maximum Symbol Exposure
        curr_sym_exp = exposure_risk.symbol_exposure.get(symbol, 0.0)
        total_sym_exp = curr_sym_exp + req_val
        if total_sym_exp > config.max_symbol_exposure:
            self._add_violation(
                "RE_MSE_001",
                "Maximum Symbol Exposure Breached",
                f"Total exposure for {symbol} of ${total_sym_exp:,.2f} > limit ${config.max_symbol_exposure:,.2f}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 15. Maximum Sector Exposure
        # Identify sector (default to layer 1 fallback if not passed)
        sector = str(kwargs.get("sector", "Layer1"))
        curr_sec_exp = exposure_risk.sector_exposure.get(sector, 0.0)
        total_sec_exp = curr_sec_exp + req_val
        if total_sec_exp > config.max_sector_exposure:
            self._add_violation(
                "RE_MSEC_001",
                "Maximum Sector Exposure Breached",
                f"Total exposure for sector {sector} of ${total_sec_exp:,.2f} > limit ${config.max_sector_exposure:,.2f}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 16. Maximum Portfolio Exposure
        total_port_exp = portfolio_risk.gross_exposure + req_val
        if total_port_exp > config.max_portfolio_exposure:
            self._add_violation(
                "RE_MPE_001",
                "Maximum Portfolio Exposure Breached",
                f"Total portfolio gross exposure ${total_port_exp:,.2f} > limit ${config.max_portfolio_exposure:,.2f}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 17. Maximum Correlation Exposure
        correlation = float(kwargs.get("correlation", 0.0))
        if abs(correlation) >= config.max_correlation_exposure:
            self._add_violation(
                "RE_MCE_001",
                "Maximum Correlation Exposure Breached",
                f"Asset correlation {correlation:.2f} >= limit {config.max_correlation_exposure:.2f}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 18. Maximum Leverage
        if leverage > config.max_leverage:
            self._add_violation(
                "RE_MLEV_001",
                "Maximum Leverage Breached",
                f"Requested leverage {leverage} > limit {config.max_leverage}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 19. Maximum Margin Usage
        expected_margin = portfolio_risk.portfolio_heat + margin_required
        margin_pct = expected_margin / account_risk.equity if account_risk.equity > 0 else 0.0
        if margin_pct > config.max_margin_usage:
            self._add_violation(
                "RE_MMU_001",
                "Maximum Margin Usage Breached",
                f"Projected margin usage {margin_pct*100:.2f}% > limit {config.max_margin_usage*100:.2f}%.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 20. Maximum Heat
        # Heat represents total portfolio margin locked
        if expected_margin > config.max_heat * account_risk.equity:
            self._add_violation(
                "RE_MHEAT_001",
                "Maximum Portfolio Heat Breached",
                f"Projected heat {expected_margin:.2f} > limit {config.max_heat * account_risk.equity:.2f}.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 21. Maximum Open Risk
        # Open risk is target stop-loss distance * quantity
        open_risk_val = float(kwargs.get("open_risk_value", 0.0))
        open_risk_pct = open_risk_val / account_risk.equity if account_risk.equity > 0 else 0.0
        if open_risk_pct > config.max_open_risk:
            self._add_violation(
                "RE_MOR_001",
                "Maximum Open Risk Breached",
                f"Projected open risk {open_risk_pct*100:.2f}% > limit {config.max_open_risk*100:.2f}%.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 22. Maximum Unrealized Loss
        unrealized_loss_pct = abs(float(kwargs.get("unrealized_loss_pct", 0.0)))
        if unrealized_loss_pct >= config.max_unrealized_loss:
            self._add_violation(
                "RE_MUL_001",
                "Maximum Unrealized Loss Breached",
                f"Current unrealized loss {unrealized_loss_pct*100:.2f}% >= limit {config.max_unrealized_loss*100:.2f}%.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 23. Minimum Liquidity
        liquidity_depth = float(kwargs.get("liquidity_depth", config.min_liquidity_depth + 1.0))
        if liquidity_depth < config.min_liquidity_depth:
            self._add_violation(
                "RE_MINLIQ",
                "Minimum Liquidity Breach",
                f"Available liquidity depth ${liquidity_depth:,.2f} < required ${config.min_liquidity_depth:,.2f}.",
                RiskSeverity.MEDIUM,
                10.0,
                factors,
                violations,
            )

        # 24. Maximum Spread
        spread = float(kwargs.get("spread", 0.0))
        if spread > config.max_spread:
            self._add_violation(
                "RE_MAXSPD",
                "Maximum Spread Breach",
                f"Market spread {spread*100:.2f}% > limit {config.max_spread*100:.2f}%.",
                RiskSeverity.MEDIUM,
                10.0,
                factors,
                violations,
            )

        # 25. Maximum Slippage
        slippage = float(kwargs.get("slippage", 0.0))
        if slippage > config.max_slippage:
            self._add_violation(
                "RE_MAXSLP",
                "Maximum Slippage Breach",
                f"Expected slippage {slippage*100:.2f}% > limit {config.max_slippage*100:.2f}%.",
                RiskSeverity.MEDIUM,
                10.0,
                factors,
                violations,
            )

        # 26. Weekend Restrictions
        is_weekend = bool(kwargs.get("is_weekend", False))
        if config.weekend_restrictions and is_weekend:
            self._add_violation(
                "RE_WKD_001",
                "Weekend Restrictions Active",
                "Trading is restricted during weekend hours.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # 27. News Lock
        if config.news_lock:
            self._add_violation(
                "RE_NEW_001",
                "News Lock Active",
                "Trading restricted due to high-impact upcoming news announcement.",
                RiskSeverity.HIGH,
                25.0,
                factors,
                violations,
            )

        # Deduct penalties and map decision
        for factor in factors:
            total_penalty += factor.score

        overall_score = max(0.0, min(100.0, 100.0 - total_penalty))

        has_critical = any(f.severity == RiskSeverity.CRITICAL for f in factors)
        has_high = any(f.severity == RiskSeverity.HIGH for f in factors)

        if overall_score < 80.0 or has_critical:
            decision = RiskDecision.BLOCK
        elif (80.0 <= overall_score < 85.0) or has_high:
            decision = RiskDecision.REVIEW
        else:
            decision = RiskDecision.ALLOW

        assessment = RiskAssessment(
            overall_score=round(overall_score, 2),
            decision=decision,
            factors=factors,
            violations=violations,
        )

        return RiskState(
            symbol=symbol,
            timeframe=timeframe,
            assessment=assessment,
            account_risk=account_risk,
            portfolio_risk=portfolio_risk,
            exposure_risk=exposure_risk,
            drawdown_risk=drawdown_risk,
            margin_risk=margin_risk,
            leverage_risk=leverage_risk,
            circuit_breaker=circuit_breaker,
            metrics=metrics,
            config=config,
            updated_at=datetime.now(timezone.utc),
        )

    def _add_violation(
        self,
        rule_id: str,
        name: str,
        message: str,
        severity: RiskSeverity,
        score: float,
        factors: list[RiskFactor],
        violations: list[RiskViolation],
    ) -> None:
        factors.append(
            RiskFactor(
                id=rule_id,
                name=name,
                severity=severity,
                score=score,
                description=message,
            )
        )
        violations.append(
            RiskViolation(
                rule_id=rule_id,
                severity=severity,
                message=message,
                timestamp=datetime.now(timezone.utc),
            )
        )
