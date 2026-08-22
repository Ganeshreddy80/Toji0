"""Authoritative Backtest Orchestrator coordinating historical replay, matching, ledger, and equity engines (Sprint 7A)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backtesting_engine.broker.simulated_broker import SimulatedBroker
from backtesting_engine.core.enums import (
    OrderType,
    PositionSide,
    ReplayStatus,
    SimulatedOrderStatus,
    TimeInForce,
)
from backtesting_engine.core.events import (
    BacktestCompleted,
    ExecutionCompleted,
    ExecutionDelayed,
    LiquidityLimited,
    PartialFillGenerated,
    ReplayFailed,
    ReplayStarted,
)
from backtesting_engine.core.exceptions import BacktestOrchestratorError
from backtesting_engine.core.interfaces import (
    IBacktestOrchestrator,
    IBacktestRepository,
    IEquityEngine,
    IHistoricalReplayEngine,
    IOrderMatchingEngine,
    ISimulatedBroker,
    ITradeLedger,
)
from backtesting_engine.core.models import (
    BacktestConfig,
    BacktestResult,
    ExecutionReport,
    MarketBar,
    SimulatedFill,
    TradeRecord,
)
from backtesting_engine.core.repository import BacktestRepository
from backtesting_engine.core.state import BacktestStateStore
from backtesting_engine.equity.equity_engine import EquityEngine
from backtesting_engine.ledger.trade_ledger import TradeLedger
from backtesting_engine.matching.execution_realism import LiquidityEngine
from backtesting_engine.matching.order_matching_engine import OrderMatchingEngine
from backtesting_engine.replay.historical_replay_engine import HistoricalReplayEngine
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class BacktestOrchestrator(IBacktestOrchestrator):
    """Authoritative coordinator executing backtest pipelines with fail-closed error handling, atomic persistence, and event broadcasts."""

    def __init__(
        self,
        replay_engine: Optional[IHistoricalReplayEngine] = None,
        broker: Optional[ISimulatedBroker] = None,
        matching_engine: Optional[IOrderMatchingEngine] = None,
        trade_ledger: Optional[ITradeLedger] = None,
        equity_engine: Optional[IEquityEngine] = None,
        repository: Optional[IBacktestRepository] = None,
        event_bus: Optional[IEventBus] = None,
        container: Optional[IContainer] = None,
    ) -> None:
        self._replay_engine: Optional[IHistoricalReplayEngine] = None
        self._broker: Optional[ISimulatedBroker] = None
        self._matching_engine: Optional[IOrderMatchingEngine] = None
        self._trade_ledger: Optional[ITradeLedger] = None
        self._equity_engine: Optional[IEquityEngine] = None
        self._repository: IBacktestRepository = BacktestRepository()
        self._state_store: BacktestStateStore = BacktestStateStore()
        self._event_bus: Optional[IEventBus] = None
        self._container: Optional[IContainer] = None

        self.initialize(
            replay_engine=replay_engine,
            broker=broker,
            matching_engine=matching_engine,
            trade_ledger=trade_ledger,
            equity_engine=equity_engine,
            repository=repository,
            event_bus=event_bus,
            container=container,
        )

    def initialize(
        self,
        replay_engine: Optional[IHistoricalReplayEngine] = None,
        broker: Optional[ISimulatedBroker] = None,
        matching_engine: Optional[IOrderMatchingEngine] = None,
        trade_ledger: Optional[ITradeLedger] = None,
        equity_engine: Optional[IEquityEngine] = None,
        repository: Optional[IBacktestRepository] = None,
        event_bus: Optional[IEventBus] = None,
        container: Optional[IContainer] = None,
    ) -> None:
        """Inject component dependencies into the orchestrator."""
        self._replay_engine = replay_engine
        self._broker = broker
        self._matching_engine = matching_engine
        self._trade_ledger = trade_ledger
        self._equity_engine = equity_engine
        self._repository = repository or self._repository
        self._event_bus = event_bus
        self._container = container

    def run_backtest(
        self,
        config: BacktestConfig,
        bars: List[MarketBar],
        orders_to_place: Optional[List[Dict[str, Any]]] = None,
    ) -> BacktestResult:
        """Execute an event-driven historical backtest pipeline end-to-end with fail-closed error handling."""
        replay_session_id = f"session-{str(uuid.uuid4())[:8]}"

        if not config or not bars:
            return self._fail_closed(
                config or BacktestConfig(start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc)),
                replay_session_id,
                "No backtest configuration or historical market bars provided.",
            )

        try:
            # Instantiate pipeline engine components
            replay_engine = self._replay_engine or HistoricalReplayEngine(bars=bars, event_bus=self._event_bus)
            broker = self._broker or SimulatedBroker(event_bus=self._event_bus)
            matching_engine = self._matching_engine or OrderMatchingEngine(event_bus=self._event_bus)
            trade_ledger = self._trade_ledger or TradeLedger(event_bus=self._event_bus)
            equity_engine = self._equity_engine or EquityEngine(initial_capital=config.initial_capital)
            liquidity_engine = LiquidityEngine(max_volume_pct=config.max_volume_pct)

            replay_engine.start()

            # Place initial orders if provided
            if orders_to_place:
                for ord_spec in orders_to_place:
                    broker.place_order(
                        symbol=ord_spec.get("symbol", bars[0].symbol),
                        side=PositionSide(ord_spec.get("side", "LONG")),
                        quantity=float(ord_spec.get("quantity", 1.0)),
                        order_type=OrderType(ord_spec.get("order_type", "MARKET")),
                        price=float(ord_spec.get("price", 0.0)),
                        stop_price=float(ord_spec.get("stop_price", 0.0)),
                        time_in_force=TimeInForce(ord_spec.get("time_in_force", "GTC")),
                        config=config,
                    )

            all_fills: List[SimulatedFill] = []
            all_reports: List[ExecutionReport] = []
            order_submission_bars: Dict[str, int] = {}
            bar_counter = 0

            # Replay historical bars sequentially
            while True:
                bar = replay_engine.step()
                if bar is None:
                    break

                bar_counter += 1
                liquidity_engine.reset_bar(bar, config)

                # Match open broker orders against replayed bar (ACCEPTED or PARTIALLY_FILLED)
                active_orders = broker.list_orders(status=SimulatedOrderStatus.ACCEPTED)
                partially_filled_orders = broker.list_orders(status=SimulatedOrderStatus.PARTIALLY_FILLED)
                candidate_orders = active_orders + partially_filled_orders

                eligible_orders: List[Any] = []
                for ord_obj in candidate_orders:
                    if ord_obj.order_id not in order_submission_bars:
                        order_submission_bars[ord_obj.order_id] = bar_counter

                    # 6. Latency Simulation: Delay execution by configured latency_bars
                    if config.latency_bars > 0 and bar_counter < order_submission_bars[ord_obj.order_id] + config.latency_bars:
                        if self._event_bus:
                            self._event_bus.publish(
                                ExecutionDelayed(
                                    source="backtesting.orchestrator",
                                    payload={"order_id": ord_obj.order_id, "delay_bars": config.latency_bars},
                                )
                            )
                        continue

                    eligible_orders.append(ord_obj)

                if eligible_orders:
                    fills = matching_engine.match_orders(eligible_orders, bar, config, liquidity_engine)
                    for fill in fills:
                        all_fills.append(fill)

                        # Update order status in broker
                        order = broker.get_order(fill.order_id)
                        if order:
                            cum_qty = order.filled_quantity + fill.fill_quantity
                            is_filled = cum_qty >= order.quantity
                            updated_status = SimulatedOrderStatus.FILLED if is_filled else SimulatedOrderStatus.PARTIALLY_FILLED

                            # Finding 007: Calculate weighted average fill price across partial fills
                            prev_filled = order.filled_quantity
                            if prev_filled > 0 and cum_qty > 0:
                                weighted_avg = ((order.avg_fill_price * prev_filled) + (fill.fill_price * fill.fill_quantity)) / cum_qty
                            else:
                                weighted_avg = fill.fill_price

                            updated_order = order.model_copy(
                                update={
                                    "status": updated_status,
                                    "filled_quantity": cum_qty,
                                    "avg_fill_price": round(weighted_avg, config.tick_precision),
                                    "updated_at": datetime.now(timezone.utc),
                                }
                            )
                            broker.update_order(updated_order)

                            # 10. Execution Report Generation
                            rem_qty = max(0.0, round(order.quantity - cum_qty, config.lot_precision))
                            report = ExecutionReport(
                                backtest_id=config.backtest_id,
                                order_id=fill.order_id,
                                symbol=fill.symbol,
                                side=fill.side,
                                requested_quantity=order.quantity,
                                executed_quantity=fill.fill_quantity,
                                remaining_quantity=rem_qty,
                                avg_fill_price=round(weighted_avg, config.tick_precision),
                                slippage=fill.slippage,
                                commission=fill.fee,
                                latency_bars=config.latency_bars,
                                liquidity_restricted=(rem_qty > 0.0 and bar.volume > 0.0),
                                status=updated_status,
                                timestamp=bar.timestamp,
                            )
                            all_reports.append(report)

                            if self._event_bus:
                                if is_filled:
                                    self._event_bus.publish(
                                        ExecutionCompleted(
                                            source="backtesting.orchestrator",
                                            payload={"order_id": order.order_id, "fill_id": fill.fill_id},
                                        )
                                    )
                                else:
                                    self._event_bus.publish(
                                        PartialFillGenerated(
                                            source="backtesting.orchestrator",
                                            payload={"order_id": order.order_id, "filled_qty": fill.fill_quantity, "remaining_qty": rem_qty},
                                        )
                                    )

                        # Process fill in trade ledger
                        trade_ledger.process_fill(fill, bar)

                    # Immediate cancellation for unexecuted/partially-executed IOC and unexecuted FOK orders
                    for cand_ord in eligible_orders:
                        current_ord = broker.get_order(cand_ord.order_id)
                        if current_ord and current_ord.time_in_force in (TimeInForce.IOC, TimeInForce.FOK):
                            if current_ord.status in (SimulatedOrderStatus.ACCEPTED, SimulatedOrderStatus.PARTIALLY_FILLED):
                                broker.cancel_order(current_ord.order_id)

                # Update equity calculator and record snapshot point
                equity_engine.update(bar, trade_ledger)

            # Pipeline execution completed successfully
            returns_series = equity_engine.get_returns_series()
            equity_curve = equity_engine.get_equity_curve()
            snapshots = equity_engine.get_snapshots()
            all_trades = trade_ledger.get_closed_trades() + trade_ledger.get_open_trades()
            final_eq = snapshots[-1].equity if snapshots else config.initial_capital

            result = BacktestResult(
                backtest_id=config.backtest_id,
                config=config,
                replay_session_id=replay_session_id,
                status=ReplayStatus.COMPLETED,
                returns_series=returns_series,
                equity_curve=equity_curve,
                equity_snapshots=snapshots,
                trades=all_trades,
                fills=all_fills,
                final_equity=final_eq,
                completed_at=datetime.now(timezone.utc),
            )

            # Option A atomic persistence: Authoritative repository first, transient state store second
            self._repository.save_result(result)
            self._state_store.save_result(result)

            if self._event_bus:
                self._event_bus.publish(
                    BacktestCompleted(
                        source="backtesting.orchestrator",
                        payload={"backtest_id": result.backtest_id, "final_equity": result.final_equity},
                    )
                )

            logger.info("BacktestOrchestrator: Completed backtest %s with final equity %f", result.backtest_id, result.final_equity)
            return result

        except Exception as e:
            logger.error("BacktestOrchestrator: Backtest %s failed execution: %s. Failing closed.", config.backtest_id, e, exc_info=True)
            return self._fail_closed(config, replay_session_id, str(e))

    def _fail_closed(self, config: BacktestConfig, replay_session_id: str, error_msg: str) -> BacktestResult:
        """Fail closed safely without re-raising or corrupting state stores."""
        failed_result = BacktestResult(
            backtest_id=config.backtest_id,
            config=config,
            replay_session_id=replay_session_id,
            status=ReplayStatus.FAILED,
            final_equity=config.initial_capital,
            error_message=error_msg,
            completed_at=datetime.now(timezone.utc),
        )

        try:
            # Finding 003: Authoritative repository persistence first; state store updated only if repository write succeeds
            self._repository.save_result(failed_result)
            self._state_store.save_result(failed_result)
        except Exception as e:
            logger.error("BacktestOrchestrator: Failed to persist failed backtest result to repository: %s", e, exc_info=True)

        if self._event_bus:
            self._event_bus.publish(
                ReplayFailed(
                    source="backtesting.orchestrator",
                    payload={"backtest_id": config.backtest_id, "error": error_msg},
                )
            )

        return failed_result

    def get_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """Fetch a persisted backtest result by ID."""
        return self._repository.load_result(backtest_id)

    @property
    def repository(self) -> IBacktestRepository:
        return self._repository
