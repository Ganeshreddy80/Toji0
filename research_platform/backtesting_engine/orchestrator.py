"""Backtesting Engine Orchestrator implementing execution loops and analytics calculation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from toji_platform.core.event_bus import IEventBus

from research_platform.backtesting_engine.analytics import BacktestAnalytics
from research_platform.backtesting_engine.events import (
    BacktestCompleted,
    OrderAccepted,
    OrderFilled,
    OrderSubmitted,
    PortfolioUpdated,
    StrategySignalGenerated
)
from research_platform.backtesting_engine.matching import MatchingEngine
from research_platform.backtesting_engine.models import (
    BacktestConfiguration,
    BacktestResult,
    BacktestRun,
    MarketEvent,
    Order,
    OrderRequest,
    PortfolioState,
    Trade
)
from research_platform.backtesting_engine.portfolio import PortfolioTracker
from research_platform.backtesting_engine.replay import HistoricalReplayEngine
from research_platform.backtesting_engine.repository import BacktestRepository
from research_platform.backtesting_engine.risk import SimulationRiskController
from research_platform.strategy_lab.models import StrategyDefinition

logger = logging.getLogger(__name__)


class BacktestingEngineOrchestrator:
    """Manages strategy loading, market event loop replays, matching queues, and updates curves."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = BacktestRepository()

    @property
    def repository(self) -> BacktestRepository:
        return self._repo

    def run_backtest(
        self,
        config: BacktestConfiguration,
        data_df: pd.DataFrame,
        strategy: StrategyDefinition
    ) -> BacktestResult:
        """Execute the event-driven backtesting replay loop."""
        run_id = str(uuid.uuid4())
        
        # Initialize subcomponents
        replay = HistoricalReplayEngine(data_df, symbol="BTC/USDT")
        replay.set_time(config.start_time)

        # Matching Engine config values
        slippage_val = config.slippage.params.get("percentage", 0.0005)
        commission_val = config.commission.params.get("percentage", 0.001)
        matching = MatchingEngine(slippage_pct=slippage_val, commission_pct=commission_val)

        portfolio = PortfolioTracker(
            initial_capital=config.initial_capital,
            margin_requirement_pct=config.margin.initial_margin_pct
        )
        risk = SimulationRiskController(
            max_drawdown_pct=0.20,
            maintenance_margin_pct=config.margin.maintenance_margin_pct
        )

        equity_curve: List[float] = [config.initial_capital]
        trades_pnl: List[float] = []
        pending_orders: List[Order] = []
        
        # Replay event loop
        while replay.has_next():
            event = replay.next_event()
            if not event:
                continue

            # 1. Update matching engine with prices
            fills = matching.match_orders(pending_orders, event)
            
            # Process order fills
            for fill in fills:
                # Find matching order
                order = next((o for o in pending_orders if o.order_id == fill.order_id), None)
                if order:
                    # Update order status to filled
                    updated_order = Order(
                        order_id=order.order_id,
                        request=order.request,
                        status="FILLED",
                        filled_quantity=fill.quantity,
                        avg_fill_price=fill.price,
                        created_time=order.created_time,
                        updated_time=event.timestamp
                    )
                    self._repo.save_order(updated_order)
                    # Remove from pending queue
                    pending_orders = [o for o in pending_orders if o.order_id != fill.order_id]

                    # Process fill in portfolio
                    p_state = portfolio.process_fill(fill)
                    self._event_bus.publish(
                        OrderFilled(
                            payload={
                                "order_id": fill.order_id,
                                "price": fill.price,
                                "qty": fill.quantity
                            }
                        )
                    )

                    # Log closed trade if applicable
                    trade = Trade(
                        trade_id=str(uuid.uuid4()),
                        order_id=fill.order_id,
                        symbol=fill.symbol,
                        direction=order.request.direction,
                        quantity=fill.quantity,
                        price=fill.price,
                        realized_pnl=p_state.realized_pnl - sum(trades_pnl),
                        commission=fill.commission,
                        slippage=fill.slippage,
                        timestamp=event.timestamp
                    )
                    self._repo.save_trade(run_id, trade)
                    trades_pnl.append(trade.realized_pnl)

            # 2. Mark portfolio to market
            state = portfolio.mark_to_market(event)
            equity_curve.append(state.equity)
            self._event_bus.publish(PortfolioUpdated(payload={"equity": state.equity}))

            # 3. Check Risk halts
            should_stop, reason = risk.check_risk(state)
            if should_stop:
                logger.warning("Simulation halted by risk engine: %s", reason)
                break

            # 4. Invoke strategy rules to generate signals
            # Combine entry rules
            close_price = event.data.get("close", 0.0)
            
            # Simple threshold check for testing strategy entry triggers
            entry_triggered = False
            for entry_rule in strategy.entry_rules:
                if entry_rule.condition_type == "SignalThreshold":
                    col = entry_rule.parameters.get("column", "close")
                    thresh = entry_rule.parameters.get("threshold", 0.0)
                    op = entry_rule.parameters.get("operator", ">")
                    
                    val = event.data.get(col, close_price)
                    if op == ">" and val > thresh:
                        entry_triggered = True
                    elif op == "<" and val < thresh:
                        entry_triggered = True

            # If triggered and no position is open, generate Buy order
            symbol = "BTC/USDT"
            if entry_triggered and symbol not in portfolio.positions:
                self._event_bus.publish(StrategySignalGenerated(payload={"strategy_id": strategy.strategy_id}))
                
                req = OrderRequest(
                    order_id=str(uuid.uuid4()),
                    strategy_id=strategy.strategy_id,
                    symbol=symbol,
                    direction="BUY",
                    quantity=1.0,
                    order_type="MARKET"
                )
                order = Order(
                    order_id=req.order_id,
                    request=req,
                    status="SUBMITTED",
                    created_time=event.timestamp,
                    updated_time=event.timestamp
                )
                self._repo.save_order(order)
                pending_orders.append(order)
                self._event_bus.publish(OrderSubmitted(payload={"order_id": order.order_id}))

            # Check exits
            if symbol in portfolio.positions:
                pos = portfolio.positions[symbol]
                exit_triggered = False
                for exit_rule in strategy.exit_rules:
                    if exit_rule.condition_type == "StopLoss":
                        stop_pct = exit_rule.parameters.get("stop_pct", 0.02)
                        stop_price = pos.avg_entry_price * (1.0 - stop_pct)
                        if close_price <= stop_price:
                            exit_triggered = True
                    elif exit_rule.condition_type == "ProfitTarget":
                        pt_pct = exit_rule.parameters.get("target_pct", 0.05)
                        target_price = pos.avg_entry_price * (1.0 + pt_pct)
                        if close_price >= target_price:
                            exit_triggered = True

                if exit_triggered:
                    req = OrderRequest(
                        order_id=str(uuid.uuid4()),
                        strategy_id=strategy.strategy_id,
                        symbol=symbol,
                        direction="SELL",
                        quantity=-pos.quantity,  # reverse/close position
                        order_type="MARKET"
                    )
                    order = Order(
                        order_id=req.order_id,
                        request=req,
                        status="SUBMITTED",
                        created_time=event.timestamp,
                        updated_time=event.timestamp
                    )
                    self._repo.save_order(order)
                    pending_orders.append(order)
                    self._event_bus.publish(OrderSubmitted(payload={"order_id": order.order_id}))

        # 5. Compute Final Performance Metrics
        stats = BacktestAnalytics.calculate_stats(equity_curve, trades_pnl, config.initial_capital)
        
        result = BacktestResult(
            run_id=run_id,
            configuration=config,
            stats=stats,
            report_json=f'{{"total_trades": {stats.total_trades}}}',
            timestamp=datetime.now(timezone.utc)
        )

        run = BacktestRun(
            run_id=run_id,
            configuration=config,
            status="COMPLETED",
            result=result,
            timestamp=datetime.now(timezone.utc)
        )
        self._repo.save_run(run)

        # Publish final completion event
        self._event_bus.publish(BacktestCompleted(payload={"run_id": run_id, "win_rate": stats.win_rate}))
        logger.info("Backtest run %s completed. Win rate: %.2f", run_id, stats.win_rate)

        return result
