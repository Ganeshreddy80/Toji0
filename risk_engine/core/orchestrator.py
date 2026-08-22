"""Risk Orchestrator for managing evaluations, persistence, and event dispatching."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.exceptions import OrchestratorError
from risk_engine.core.interfaces import (
    IRiskEngine,
    IRiskRepository,
    IRiskStateStore,
)
from risk_engine.core.models import RiskState, RiskSnapshot
from risk_engine.core.events import (
    RiskUpdated,
    RiskApproved,
    RiskRejected,
    RiskThresholdExceeded,
)

logger = logging.getLogger(__name__)


class RiskOrchestrator:
    """Coordinates evaluating risk rules on new contexts, updating state, and broadcasting results."""

    def __init__(self) -> None:
        self._state_store: IRiskStateStore | None = None
        self._repository: IRiskRepository | None = None
        self._risk_engine: IRiskEngine | None = None
        self._event_bus: IEventBus | None = None
        self._config_provider: IConfigProvider | None = None
        self._container: IContainer | None = None

    def initialize(
        self,
        state_store: IRiskStateStore,
        repository: IRiskRepository,
        risk_engine: IRiskEngine,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._state_store = state_store
        self._repository = repository
        self._risk_engine = risk_engine
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container

        # Resolve missing services from the DI container if available
        if container is not None:
            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
            if self._config_provider is None and container.has(IConfigProvider):
                self._config_provider = container.resolve(IConfigProvider)

    def process_context(self, context: TradingContext, **kwargs: Any) -> RiskState | None:
        """Evaluate context risk, update store, save snapshot, and dispatch events."""
        if not self._state_store or not self._repository or not self._risk_engine:
            raise OrchestratorError("RiskOrchestrator is not initialized.")

        try:
            symbol = context.symbol
            timeframe = context.timeframe

            # 1. Compile configuration options
            config_params = {}
            if self._config_provider:
                # Core limit thresholds
                config_params["daily_loss_limit_pct"] = self._config_provider.get("risk.daily_loss_limit_pct", 0.02)
                config_params["max_daily_trades"] = self._config_provider.get("risk.max_daily_trades", 10)
                config_params["max_drawdown_pct"] = self._config_provider.get("risk.max_drawdown_pct", 0.05)
                config_params["equity_protection_pct"] = self._config_provider.get("risk.equity_protection_pct", 0.10)
                config_params["volatility_threshold_multiplier"] = self._config_provider.get("risk.volatility_threshold_multiplier", 3.0)
                config_params["max_correlation_limit"] = self._config_provider.get("risk.max_correlation_limit", 0.7)
                config_params["max_allowable_spread"] = self._config_provider.get("risk.max_allowable_spread", 0.005)
                config_params["min_required_volume"] = self._config_provider.get("risk.min_required_volume", 1.0)
                config_params["weekend_block_active"] = self._config_provider.get("risk.weekend_block_active", True)
                config_params["weekend_start_hour"] = self._config_provider.get("risk.weekend_start_hour", 17)
                config_params["weekend_end_hour"] = self._config_provider.get("risk.weekend_end_hour", 18)

            # Override/supplement with explicit runtime kwargs
            eval_kwargs = {**config_params, **kwargs}

            # 2. Run risk assessment
            assessment = self._risk_engine.evaluate(context, **eval_kwargs)

            # 3. Construct RiskState
            risk_state = RiskState(
                symbol=symbol,
                timeframe=timeframe,
                assessment=assessment,
                updated_at=datetime.now(timezone.utc),
            )

            # 4. Fetch previous snapshot
            prev_snapshot = self._state_store.get_snapshot(symbol)
            if prev_snapshot is None:
                prev_snapshot = RiskSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=risk_state.updated_at,
                    states={},
                )
                self._state_store.update_snapshot(prev_snapshot)

            # 5. Update state store
            updated_snapshot = self._state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=risk_state,
            )

            # 6. Save to repository
            self._repository.save_snapshot(updated_snapshot)

            # 7. Dispatch events
            self._dispatch_events(risk_state)

            return risk_state

        except Exception as e:
            logger.error("RiskOrchestrator: Evaluation failed: %s", e)
            raise OrchestratorError(f"Failed to process risk assessment: {e}") from e

    def _dispatch_events(self, risk_state: RiskState) -> None:
        """Publish updated/approved/rejected events to the event bus."""
        if not self._event_bus:
            return

        symbol = risk_state.symbol
        timeframe = risk_state.timeframe
        source = "risk_engine.orchestrator"
        state_json = risk_state.model_dump(mode="json")
        assessment = risk_state.assessment

        # 1. Publish system.risk_updated
        self._event_bus.publish(
            RiskUpdated(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "state": state_json,
                },
            )
        )

        # Publish RiskChecked event for downstream pipelines
        from toji_platform.core.event_bus.events import RiskChecked
        rc_event = RiskChecked(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "state": state_json,
                "decision": assessment.decision.value,
            },
        )
        self._event_bus.publish(rc_event)

        # 2. Publish decision events
        if assessment.decision == RiskDecision.ALLOW:
            self._event_bus.publish(
                RiskApproved(
                    source=source,
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "state": state_json,
                    },
                )
            )
        elif assessment.decision == RiskDecision.BLOCK:
            primary_reason = assessment.violations[0] if assessment.violations else "Risk check rejected."
            self._event_bus.publish(
                RiskRejected(
                    source=source,
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "state": state_json,
                        "reason": primary_reason,
                    },
                )
            )

        # 3. Publish threshold exceeded events if applicable
        has_critical = any(f.severity == RiskSeverity.CRITICAL for f in assessment.factors)
        if assessment.overall_score < 80.0 or has_critical:
            msg = f"Critical risk threshold breach: score={assessment.overall_score:.2f}, critical={has_critical}."
            self._event_bus.publish(
                RiskThresholdExceeded(
                    source=source,
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "state": state_json,
                        "message": msg,
                    },
                )
            )

    def process_execution_request(self, payload: dict[str, Any]) -> RiskState:
        """Evaluate pre-trade execution request against all institutional risk rules."""
        from risk_engine.analysis.rules_engine import RiskRulesEngine
        from risk_engine.analysis.drawdown_engine import DrawdownEngine
        from risk_engine.analysis.exposure_engine import ExposureEngine
        from risk_engine.analysis.circuit_breakers import CircuitBreakerEngine
        from risk_engine.core.events import (
            RiskEvaluated,
            RiskApproved,
            RiskRejected,
            RiskLimitExceeded,
            DrawdownUpdated,
            ExposureUpdated,
            CircuitBreakerTriggered,
            CircuitBreakerReleased,
            PortfolioRiskUpdated,
            PositionRiskUpdated,
            RiskUpdated,
        )
        from execution_engine.core.events import ExecutionApproved
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

        # --- Fail-Closed Payload Validation (RE_PAYLOAD_001) ---
        # Required fields: symbol, quantity, price.
        # Missing or invalid values MUST block immediately — no calculation on fabricated inputs.
        symbol = payload.get("symbol")
        timeframe = payload.get("timeframe")
        raw_qty = payload.get("quantity")
        raw_price = payload.get("price")

        missing_fields = []
        if not symbol or not str(symbol).strip():
            missing_fields.append("symbol")
        if raw_qty is None:
            missing_fields.append("quantity")
        elif float(raw_qty) <= 0:
            missing_fields.append("quantity (must be > 0)")
        if raw_price is None:
            missing_fields.append("price")
        elif float(raw_price) <= 0:
            missing_fields.append("price (must be > 0)")

        if missing_fields:
            from risk_engine.core.models import RiskAssessment, RiskViolation
            msg = (
                f"Payload validation failed — missing or invalid required field(s): "
                f"{', '.join(missing_fields)}. "
                "Trade blocked to prevent evaluation on fabricated inputs."
            )
            logger.error(
                "RiskOrchestrator.process_execution_request: RE_PAYLOAD_001 — %s",
                msg,
            )
            block_assessment = RiskAssessment(
                overall_score=0.0,
                decision=RiskDecision.BLOCK,
                factors=[],
                violations=[
                    RiskViolation(
                        rule_id="RE_PAYLOAD_001",
                        severity=RiskSeverity.CRITICAL,
                        message=msg,
                    )
                ],
            )
            # Use safe fallbacks only for the returned model's identity fields,
            # never for financial calculations.
            safe_symbol = str(symbol) if symbol else "UNKNOWN"
            safe_timeframe = str(timeframe) if timeframe else "UNKNOWN"
            return RiskState(
                symbol=safe_symbol,
                timeframe=safe_timeframe,
                assessment=block_assessment,
            )

        # All required fields are confirmed present and valid.
        symbol = str(symbol)
        timeframe = str(timeframe) if timeframe else "UNKNOWN"
        qty = float(raw_qty)
        price = float(raw_price)
        leverage = float(payload.get("leverage", 1.0))
        margin_required = float(payload.get("margin_required", 0.0))

        # 1. Resolve configurations
        config_params = {}
        if self._config_provider:
            config_params["daily_loss_limit"] = self._config_provider.get("risk.daily_loss_limit", 0.02)
            config_params["weekly_loss_limit"] = self._config_provider.get("risk.weekly_loss_limit", 0.05)
            config_params["monthly_loss_limit"] = self._config_provider.get("risk.monthly_loss_limit", 0.10)
            config_params["max_drawdown_limit"] = self._config_provider.get("risk.max_drawdown_limit", 0.15)
            config_params["max_consecutive_losses"] = self._config_provider.get("risk.max_consecutive_losses", 5)
            config_params["max_losing_streak"] = self._config_provider.get("risk.max_losing_streak", 7)
            config_params["max_open_positions"] = self._config_provider.get("risk.max_open_positions", 10)
            config_params["max_position_size"] = self._config_provider.get("risk.max_position_size", 100000.0)
            config_params["max_symbol_exposure"] = self._config_provider.get("risk.max_symbol_exposure", 50000.0)
            config_params["max_sector_exposure"] = self._config_provider.get("risk.max_sector_exposure", 150000.0)
            config_params["max_portfolio_exposure"] = self._config_provider.get("risk.max_portfolio_exposure", 500000.0)
            config_params["max_correlation_exposure"] = self._config_provider.get("risk.max_correlation_exposure", 0.7)
            config_params["max_leverage"] = self._config_provider.get("risk.max_leverage", 5.0)
            config_params["max_margin_usage"] = self._config_provider.get("risk.max_margin_usage", 0.5)
            config_params["max_heat"] = self._config_provider.get("risk.max_heat", 1.0)
            config_params["max_open_risk"] = self._config_provider.get("risk.max_open_risk", 0.05)
            config_params["max_unrealized_loss"] = self._config_provider.get("risk.max_unrealized_loss", 0.10)
            config_params["min_liquidity_depth"] = self._config_provider.get("risk.min_liquidity_depth", 10000.0)
            config_params["max_spread"] = self._config_provider.get("risk.max_spread", 0.01)
            config_params["max_slippage"] = self._config_provider.get("risk.max_slippage", 0.02)
            config_params["weekend_restrictions"] = self._config_provider.get("risk.weekend_restrictions", True)
            config_params["market_halt"] = self._config_provider.get("risk.market_halt", False)
            config_params["exchange_maintenance"] = self._config_provider.get("risk.exchange_maintenance", False)
            config_params["news_lock"] = self._config_provider.get("risk.news_lock", False)
            config_params["manual_kill_switch"] = self._config_provider.get("risk.manual_kill_switch", False)
            config_params["emergency_stop"] = self._config_provider.get("risk.emergency_stop", False)
            config_params["cooldown_period_seconds"] = self._config_provider.get("risk.cooldown_period_seconds", 300)
            config_params["risk_override"] = self._config_provider.get("risk.risk_override", False)

        config = RiskConfiguration(**config_params)

        # 2. Rebuild live metric snapshots by querying Portfolio Engine
        # Use None as sentinel — absence of financial state must fail closed, not default to phantom values.
        positions_list = []
        closed_positions = list(payload.get("closed_positions", [])) if isinstance(payload, dict) else []
        returns_history = list(payload.get("returns_history", [])) if isinstance(payload, dict) else []
        snapshot_history = list(payload.get("snapshot_history", [])) if isinstance(payload, dict) else []

        equity: float | None = float(payload["equity"]) if isinstance(payload, dict) and "equity" in payload else None
        balance: float | None = float(payload["balance"]) if isinstance(payload, dict) and "balance" in payload else None
        initial_balance: float | None = float(payload["initial_balance"]) if isinstance(payload, dict) and "initial_balance" in payload else None
        peak_balance: float | None = float(payload["peak_balance"]) if isinstance(payload, dict) and "peak_balance" in payload else None
        margin_used: float = float(payload.get("margin_used", 0.0)) if isinstance(payload, dict) else 0.0
        leverage_ratio: float = float(payload.get("leverage_ratio", 1.0)) if isinstance(payload, dict) else 1.0
        net_profit: float = float(payload.get("net_profit", 0.0)) if isinstance(payload, dict) else 0.0
        unrealized_pnl: float = float(payload.get("unrealized_pnl", 0.0)) if isinstance(payload, dict) else 0.0

        if self._container:
            try:
                from portfolio_engine.core.state import PortfolioStateStore
                if self._container.has(PortfolioStateStore):
                    portfolio_store = self._container.resolve(PortfolioStateStore)
                    snap = portfolio_store.get_current_snapshot()
                    positions_list = list(snap.positions.values())
                    closed_positions = list(snap.closed_positions)
                    snapshot_history = portfolio_store.get_history()
                    balance = snap.metrics.portfolio_value
                    equity = balance + snap.metrics.total_unrealized_pnl
                    initial_balance = getattr(portfolio_store, "_initial_balance", balance)
                    peak_balance = getattr(portfolio_store, "_peak_value", balance)
                    margin_used = snap.metrics.margin_used
                    leverage_ratio = snap.metrics.leverage_ratio
                    net_profit = snap.metrics.total_realized_pnl
                    unrealized_pnl = snap.metrics.total_unrealized_pnl
            except Exception as e:
                logger.error("RiskOrchestrator: Failed to resolve PortfolioStateStore: %s", e)

        # P0 Fail-Closed Guard: if no financial state was resolved from portfolio or payload, block the request.
        if equity is None or initial_balance is None or balance is None:
            logger.error(
                "RiskOrchestrator.process_execution_request: No portfolio state available and no financial "
                "parameters supplied in payload for symbol=%s. Failing closed — trade blocked.",
                symbol,
            )
            from risk_engine.core.models import RiskAssessment, RiskViolation
            block_assessment = RiskAssessment(
                overall_score=0.0,
                decision=RiskDecision.BLOCK,
                factors=[],
                violations=[
                    RiskViolation(
                        rule_id="RE_STATE_001",
                        severity=RiskSeverity.CRITICAL,
                        message=(
                            "No portfolio financial state available (equity/balance/initial_balance missing). "
                            "Trade blocked to prevent evaluation on fabricated account state."
                        ),
                    )
                ],
            )
            return RiskState(
                symbol=symbol,
                timeframe=timeframe,
                assessment=block_assessment,
            )

        # Resolve peak_balance now that equity and balance are confirmed non-None.
        if peak_balance is None:
            peak_balance = max(initial_balance, balance, equity)

        # 3. Instantiate sub-engines and run calculations
        drawdown_engine = DrawdownEngine()
        exposure_engine = ExposureEngine()
        circuit_engine = CircuitBreakerEngine()
        rules_engine = RiskRulesEngine()

        # Drawdown calculations
        drawdown_risk, alert_level, halt_trigger = drawdown_engine.calculate_drawdown(
            current_equity=equity,
            peak_equity=peak_balance,
            net_profit=net_profit,
            warning_threshold=config.max_drawdown_limit * 0.7,
            halt_threshold=config.max_drawdown_limit,
        )

        # Exposure calculations
        exposure_risk, portfolio_risk = exposure_engine.calculate_exposures(
            positions=positions_list,
            equity=equity,
            balance=balance,
            total_risk_budget=initial_balance * 0.5,
        )

        # Circuit breakers evaluation
        consecutive_losses = int(payload.get("consecutive_losses", 0))
        volatility_triggered = bool(payload.get("volatility_triggered", False))
        correlation_triggered = bool(payload.get("correlation_triggered", False))
        latency_triggered = bool(payload.get("latency_triggered", False))
        broker_failure = bool(payload.get("broker_failure", False))
        exchange_failure = bool(payload.get("exchange_failure", False))

        prev_cb_state = None
        prev_risk_snap = self._state_store.get_snapshot(symbol) if self._state_store else None
        if prev_risk_snap and timeframe in prev_risk_snap.states:
            prev_cb_state = prev_risk_snap.states[timeframe].circuit_breaker

        cb_state, cb_transitions = circuit_engine.evaluate_breakers(
            current_state=prev_cb_state,
            daily_loss_triggered=(alert_level == "HALT" or halt_trigger),
            weekly_loss_triggered=bool(payload.get("weekly_loss_triggered", False)),
            monthly_loss_triggered=bool(payload.get("monthly_loss_triggered", False)),
            consecutive_losses_triggered=(consecutive_losses >= config.max_consecutive_losses),
            volatility_triggered=volatility_triggered,
            correlation_triggered=correlation_triggered,
            latency_triggered=latency_triggered,
            broker_failure=broker_failure,
            exchange_failure=exchange_failure,
            manual_emergency_stop=config.emergency_stop or config.manual_kill_switch,
        )

        # Leverage & Margin status
        margin_risk = MarginRisk(
            margin_usage_pct=round(margin_used / equity, 4) if equity > 0 else 0.0,
            margin_call_level=0.8,
            liquidation_level=0.5,
        )
        leverage_risk = LeverageRisk(
            account_leverage=leverage_ratio,
            max_leverage_limit=config.max_leverage,
            leverage_utilization=round((leverage_ratio / config.max_leverage) * 100.0, 2) if config.max_leverage > 0 else 0.0,
        )

        account_risk = AccountRisk(
            balance=round(balance, 2),
            equity=round(equity, 2),
            initial_balance=round(initial_balance, 2),
            peak_balance=round(peak_balance, 2),
            net_profit=round(net_profit, 2),
            free_margin=round(equity - margin_used, 2),
            margin_usage=round(margin_used, 2),
            leverage=leverage_ratio,
        )

        # Empirical RiskMetrics calculation based on historical portfolio data
        metrics = self._calculate_empirical_metrics(
            net_profit=net_profit,
            initial_balance=initial_balance,
            max_drawdown=drawdown_risk.max_drawdown,
            closed_positions=closed_positions,
            returns_history=returns_history,
            snapshot_history=snapshot_history,
        )

        # 4. Evaluate risk state via Rules Engine
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
            circuit_breaker=cb_state,
            metrics=metrics,
            config=config,
        )

        # 5. Save state to store and repository
        if self._state_store:
            # Check/initialize symbol snapshot
            snap = self._state_store.get_snapshot(symbol)
            if not snap:
                snap = RiskSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=datetime.now(timezone.utc),
                    states={},
                )
                self._state_store.update_snapshot(snap)
            self._state_store.update_timeframe_state(symbol, timeframe, risk_state)

        if self._repository:
            latest_snap = self._state_store.get_snapshot(symbol) if self._state_store else None
            if latest_snap:
                self._repository.save_snapshot(latest_snap)

        # 6. Publish events
        if self._event_bus:
            source = "risk_engine.orchestrator"
            state_json = risk_state.model_dump(mode="json")
            decision = risk_state.assessment.decision

            # Core updates
            self._event_bus.publish(RiskEvaluated(source=source, payload=payload))
            self._event_bus.publish(RiskUpdated(source=source, payload={"symbol": symbol, "timeframe": timeframe, "state": state_json}))
            self._event_bus.publish(DrawdownUpdated(source=source, payload=drawdown_risk.model_dump()))
            self._event_bus.publish(ExposureUpdated(source=source, payload=exposure_risk.model_dump()))
            self._event_bus.publish(PortfolioRiskUpdated(source=source, payload=portfolio_risk.model_dump()))

            # Circuit breaker transitions
            for trigger_type, action in cb_transitions:
                ev_payload = {"breaker": trigger_type.name, "symbol": symbol, "timestamp": datetime.now(timezone.utc).isoformat()}
                if action == "TRIGGERED":
                    self._event_bus.publish(CircuitBreakerTriggered(source=source, payload=ev_payload))
                else:
                    self._event_bus.publish(CircuitBreakerReleased(source=source, payload=ev_payload))

            # Approval/Rejection/Review dispatching — each decision state has an explicit branch.
            # REVIEW is intentionally treated as a non-execution path under FAIL CLOSED:
            # no ExecutionApproved is published. The RiskReview event is emitted so downstream
            # consumers can trigger a manual approval workflow if desired.
            from risk_engine.core.events import RiskReview
            if decision == RiskDecision.ALLOW:
                self._event_bus.publish(ExecutionApproved(source=source, payload=payload))
            elif decision == RiskDecision.REVIEW:
                primary_reason = risk_state.assessment.violations[0].message if risk_state.assessment.violations else "Risk review required."
                logger.warning(
                    "RiskOrchestrator: REVIEW decision for %s/%s — execution held pending human approval. Reason: %s",
                    symbol, timeframe, primary_reason,
                )
                self._event_bus.publish(RiskReview(source=source, payload={"symbol": symbol, "timeframe": timeframe, "reason": primary_reason, "state": state_json}))
            elif decision == RiskDecision.BLOCK:
                primary_reason = risk_state.assessment.violations[0].message if risk_state.assessment.violations else "Risk limit breached."
                self._event_bus.publish(RiskLimitExceeded(source=source, payload={"symbol": symbol, "reason": primary_reason}))
                from execution_engine.core.events import ExecutionRejected
                self._event_bus.publish(ExecutionRejected(source=source, payload={"symbol": symbol, "reason": primary_reason}))

        return risk_state

    @staticmethod
    def _calculate_empirical_metrics(
        net_profit: float,
        initial_balance: float,
        max_drawdown: float,
        closed_positions: list[Any] | None = None,
        returns_history: list[float] | None = None,
        snapshot_history: list[Any] | None = None,
    ) -> RiskMetrics:
        """
        Calculate deterministic RiskMetrics from empirical historical portfolio returns and trade records.
        If historical portfolio data is empty, insufficient (< 2 data points for variance ratios), or invalid,
        metrics are set to 0.0 without fabricating values.
        """
        from risk_engine.core.models import RiskMetrics

        if initial_balance <= 0:
            return RiskMetrics(
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                profit_factor=0.0,
                win_rate=0.0,
                expectancy=0.0,
            )

        # 1. Trade-level metrics from closed positions (Win Rate, Profit Factor, Expectancy)
        win_rate_val = 0.0
        profit_factor_val = 0.0
        expectancy_val = 0.0

        if closed_positions and len(closed_positions) > 0:
            total_trades = len(closed_positions)
            wins = [getattr(p, "realized_pnl", 0.0) for p in closed_positions if getattr(p, "realized_pnl", 0.0) > 0.0]
            losses = [abs(getattr(p, "realized_pnl", 0.0)) for p in closed_positions if getattr(p, "realized_pnl", 0.0) < 0.0]

            total_win = sum(wins)
            total_loss = sum(losses)

            win_rate_val = round(len(wins) / total_trades, 4)

            if total_loss > 0.0:
                # Profit Factor = gross profit / gross loss (dimensionless ratio).
                profit_factor_val = round(total_win / total_loss, 4)
            else:
                # No losing trades: profit factor is undefined (not a ratio).
                # Fail-closed convention: return 0.0 rather than fabricating a value.
                profit_factor_val = 0.0

            expectancy_val = round(sum(getattr(p, "realized_pnl", 0.0) for p in closed_positions) / total_trades, 4)

        # 2. Historical returns for Sharpe and Sortino Ratios
        returns: list[float] = []

        if returns_history and len(returns_history) > 0:
            returns = [float(r) for r in returns_history]
        elif closed_positions and len(closed_positions) > 0:
            returns = [float(getattr(p, "realized_pnl", 0.0) / initial_balance) for p in closed_positions]
        elif snapshot_history and len(snapshot_history) > 1:
            for i in range(1, len(snapshot_history)):
                prev_val = getattr(snapshot_history[i - 1].metrics, "portfolio_value", 0.0)
                curr_val = getattr(snapshot_history[i].metrics, "portfolio_value", 0.0)
                if prev_val > 0:
                    returns.append((curr_val - prev_val) / prev_val)

        sharpe_ratio_val = 0.0
        sortino_ratio_val = 0.0

        # Calculate Sharpe & Sortino only if sufficient historical returns exist (at least 2 data points).
        # Convention: both ratios use sample standard deviation (denominator = n-1, Bessel's correction),
        # annualized by sqrt(252) trading days. MAR (minimum acceptable return) = 0 for Sortino.
        if len(returns) >= 2:
            n = len(returns)
            mean_return = sum(returns) / n
            # Sharpe: uses total-return std dev with sample correction (n-1).
            variance = sum((x - mean_return) ** 2 for x in returns) / (n - 1)
            std_dev = math.sqrt(variance)

            if std_dev > 0.0:
                sharpe_ratio_val = round((mean_return / std_dev) * math.sqrt(252), 4)

            # Sortino: uses downside deviation with the same sample correction (n-1) for consistency.
            # Downside returns are those below MAR=0; upward returns contribute zero downside deviation.
            downside_sq = sum((x - 0.0) ** 2 for x in returns if x < 0.0)
            if downside_sq > 0.0 and n > 1:
                downside_std = math.sqrt(downside_sq / (n - 1))
                sortino_ratio_val = round((mean_return / downside_std) * math.sqrt(252), 4)

        # 3. Calmar Ratio calculation
        calmar_ratio_val = 0.0
        if max_drawdown > 0.0 and initial_balance > 0.0:
            calmar_ratio_val = round((net_profit / initial_balance) / max_drawdown, 4)

        return RiskMetrics(
            sharpe_ratio=sharpe_ratio_val,
            sortino_ratio=sortino_ratio_val,
            calmar_ratio=calmar_ratio_val,
            profit_factor=profit_factor_val,
            win_rate=win_rate_val,
            expectancy=expectancy_val,
        )
