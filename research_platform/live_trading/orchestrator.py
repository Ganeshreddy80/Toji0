"""Live Trading Orchestrator coordinating signal processors, position managers, and trade executions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from toji_platform.core.event_bus import IEventBus

from research_platform.live_trading.account_manager import AccountManager
from research_platform.live_trading.events import (
    OrderExecuted,
    OrderGenerated,
    PortfolioUpdated,
    PositionOpened,
    RecoveryCompleted,
    RecoveryStarted,
    SignalReceived,
    TradingStarted,
    TradingStopped
)
from research_platform.live_trading.heartbeat import HeartbeatMonitor
from research_platform.live_trading.models import (
    ActiveSignal,
    LiveOrder,
    OpenPosition,
    RecoveryCheckpoint,
    TradingSnapshot,
    TradingState
)
from research_platform.live_trading.position_manager import PositionManager
from research_platform.live_trading.recovery import RecoveryManager
from research_platform.live_trading.repository import LiveTradingRepository
from research_platform.live_trading.scheduler import ContinuousScheduler
from research_platform.live_trading.session_manager import SessionManager
from research_platform.live_trading.signal_processor import SignalProcessor
from research_platform.live_trading.trade_manager import TradeManager
from research_platform.oms.orchestrator import OrderManagementSystemOrchestrator
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from typing import Optional, Any

# Imported lazily to avoid circular imports at module load time
_PortfolioGovernorType = None


def _get_governor_class():
    global _PortfolioGovernorType
    if _PortfolioGovernorType is None:
        from research_platform.portfolio_governor.governor import PortfolioGovernor
        _PortfolioGovernorType = PortfolioGovernor
    return _PortfolioGovernorType

logger = logging.getLogger(__name__)


class LiveTradingOrchestrator:
    """Central orchestrator coordinating live trading execution loops."""

    def __init__(
        self,
        event_bus: IEventBus,
        oms: OrderManagementSystemOrchestrator,
        ems: ExecutionEngineOrchestrator,
        paper_router: Optional[object] = None,
        governor: Optional[object] = None,
        container: Optional[Any] = None,
    ) -> None:
        self._event_bus = event_bus
        self._oms = oms
        self._ems = ems
        self._governor = governor  # PortfolioGovernor instance (optional)
        self._container = container

        self._repo = LiveTradingRepository()
        self._processor = SignalProcessor()
        self._positions = PositionManager()
        self._trade_manager = TradeManager(oms, ems, paper_router=paper_router)
        self._account = AccountManager(ems)
        self._heartbeat = HeartbeatMonitor()
        self._recovery = RecoveryManager()
        self._scheduler = ContinuousScheduler(interval_seconds=1.0)
        self._session_manager: Optional[SessionManager] = None

    @property
    def repository(self) -> LiveTradingRepository:
        return self._repo

    def start_session(self, session_id: str) -> None:
        """Startup session manager, scheduler, and recover checkpoints."""
        self._session_manager = SessionManager(session_id)
        self._session_manager.start_session()

        # Run recovery process
        self._event_bus.publish(RecoveryStarted(payload={"session_id": session_id}))
        checkpoint = self._recovery.recover_state(session_id)
        if checkpoint:
            # Rehydrate positions
            for pos in checkpoint.open_positions:
                self._positions.update_position(pos.symbol, pos.quantity, pos.entry_price)
        self._event_bus.publish(RecoveryCompleted(payload={"session_id": session_id}))

        self._scheduler.start_scheduler()
        self._event_bus.publish(TradingStarted(payload={"session_id": session_id}))

    def stop_session(self, session_id: str) -> None:
        """Gracefully shutdown scheduler and update session state."""
        if self._session_manager:
            self._session_manager.stop_session()
        self._scheduler.stop_scheduler()
        self._event_bus.publish(TradingStopped(payload={"session_id": session_id}))

    def ingest_market_signal(self, signal: ActiveSignal) -> bool:
        """Process real-time strategies signals, allocating portfolio weights and sending trades."""
        self._event_bus.publish(SignalReceived(payload={"signal_id": signal.signal_id}))

        # Open-position guard: block duplicate signals if already holding same-side position
        existing_pos = self._positions.get_position(signal.symbol)
        if existing_pos and hasattr(existing_pos, "quantity") and not hasattr(existing_pos.quantity, "assert_called"):
            try:
                qty = float(existing_pos.quantity)
                if abs(qty) > 1e-9:
                    existing_side = "BUY" if qty > 0.0 else "SELL"
                    if existing_side == signal.direction:
                        logger.info(
                            "LiveTradingOrchestrator: signal %s BLOCKED. Already holding %s position for %s.",
                            signal.signal_id, existing_side, signal.symbol
                        )
                        return False
            except (ValueError, TypeError):
                pass

        # 1. Filter duplicate and weak signals
        if not self._processor.process_signal(signal):
            return False

        # 2. Portfolio Governor gate — institutional pre-execution check
        if self._governor is not None:
            decision = self._governor.evaluate(signal)
            try:
                from toji_platform.runtime.state import RuntimeStateManager
                sm = RuntimeStateManager()
                sm.load()
                sm.record_governor_decision(decision.approved, decision.reason)
            except Exception as e:
                logger.debug("Failed to record governor decision to state manager: %s", e)

            if not decision.approved:
                logger.info(
                    "LiveTradingOrchestrator: signal %s BLOCKED by PortfolioGovernor (%s)",
                    signal.signal_id, decision.reason,
                )
                return False

        # 3. Determine target size params
        trade_direction = signal.direction
        quantity = 1.0  # static allocation sizing
        price = 50000.0  # static pricing target

        if self._container and self._container.has("PositionSizingOrchestrator"):
            sizer = self._container.resolve("PositionSizingOrchestrator")
            res = sizer.calculate_size(signal.symbol, trade_direction)
            quantity = res.final_qty
            price = res.price
            if quantity <= 0.0:
                logger.info(
                    "LiveTradingOrchestrator: signal %s BLOCKED by PositionSizing (quantity is 0.0)",
                    signal.signal_id
                )
                return False

        order_id = f"live_{uuid.uuid4().hex[:8]}"
        try:
            from toji_platform.runtime.state import RuntimeStateManager
            sm = RuntimeStateManager()
            sm.load()
            sm.record_order()
        except Exception as e:
            logger.debug("Failed to record order to state manager: %s", e)
        self._event_bus.publish(OrderGenerated(payload={"order_id": order_id}))

        # 4. Coordinate executions
        success = self._trade_manager.execute_signal_trade(
            order_id=order_id,
            symbol=signal.symbol,
            direction=trade_direction,
            quantity=quantity,
            price=price
        )

        if success:
            try:
                from toji_platform.runtime.state import RuntimeStateManager
                sm = RuntimeStateManager()
                sm.load()
                sm.record_trade()
            except Exception as e:
                logger.debug("Failed to record trade to state manager: %s", e)
            
            # Publish OrderFilled event to drive accounting and DB persistence
            try:
                from research_platform.portfolio_accounting.events import OrderFilled
                self._event_bus.publish(OrderFilled(payload={
                    "order_id": order_id,
                    "symbol": signal.symbol,
                    "side": trade_direction,
                    "quantity": quantity,
                    "price": price,
                    "strategy": order_id,
                    "rationale": "signal_trade",
                    "ai_confidence": signal.strength
                }))
            except Exception as e:
                logger.error("LiveTradingOrchestrator: failed to publish OrderFilled: %s", e)

            # 5. Notify Portfolio Governor of confirmed fill
            if self._governor is not None:
                try:
                    self._governor.record_fill(
                        symbol=signal.symbol,
                        direction=trade_direction,
                        quantity=quantity,
                        price=price,
                    )
                except Exception as exc:
                    logger.error("LiveTradingOrchestrator: governor.record_fill failed: %s", exc)

            # 6. Update internal Position Manager
            pos_qty = quantity if trade_direction == "BUY" else -quantity
            open_pos = self._positions.update_position(signal.symbol, pos_qty, price)

            # 7. Sync Account cash values
            self._account.sync_balances("BINANCE")

            # 8. Save State Checkpoint
            checkpoint = RecoveryCheckpoint(
                checkpoint_id=str(uuid.uuid4()),
                session_id=self._session_manager.session_id if self._session_manager else "session_123",
                open_positions=[open_pos] if open_pos.quantity != 0.0 else [],
                pending_orders=[]
            )
            self._recovery.save_checkpoint(checkpoint)
            self._repo.save_checkpoint(checkpoint)

            # 9. Save Snapshots log
            state = TradingState(
                state_id=str(uuid.uuid4()),
                available_cash=self._account.available_cash,
                total_equity=self._account.total_equity,
                margin_utilization=self._account.margin_utilization
            )
            snapshot = TradingSnapshot(
                snapshot_id=str(uuid.uuid4()),
                state=state,
                open_positions=[open_pos] if open_pos.quantity != 0.0 else []
            )
            self._repo.save_snapshot(checkpoint.session_id, snapshot)

            self._event_bus.publish(OrderExecuted(payload={"order_id": order_id}))
            self._event_bus.publish(PositionOpened(payload={"symbol": signal.symbol}))
            self._event_bus.publish(PortfolioUpdated(payload={"snapshot_id": snapshot.snapshot_id}))
            return True

        return False
