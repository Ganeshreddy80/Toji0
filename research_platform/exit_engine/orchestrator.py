"""Exit Engine Orchestrator implementing institutional-grade protective exits.
"""

from __future__ import annotations

import logging
import os
import uuid
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus
from research_platform.live_trading.orchestrator import LiveTradingOrchestrator
from research_platform.exit_engine.models import ExitEngineConfig, PositionExitState

logger = logging.getLogger(__name__)


class ExitEngineOrchestrator:
    """Monitors open position valuations and manages automated exits.

    Exit criteria:
      - Stop Loss (% or ATR)
      - Take Profit (%)
      - Trailing Stop (high watermark)
      - Break Even (move stop to entry after trigger profit)
      - Time Stop (maximum hold duration)
      - Volatility Exit (normalized ATR or risk score)
    """

    def __init__(self, event_bus: IEventBus, container: Any) -> None:
        self._event_bus = event_bus
        self._container = container
        self._lock = threading.RLock()

        # Track exit engine states
        self._exit_states: Dict[str, PositionExitState] = {}
        self._triggered_stops: List[dict] = []
        self._exit_counts: Dict[str, int] = {
            "STOP_LOSS": 0,
            "TAKE_PROFIT": 0,
            "ATR_STOP": 0,
            "TRAILING_STOP": 0,
            "BREAK_EVEN": 0,
            "TIME_STOP": 0,
            "VOLATILITY": 0,
            "AI": 0,
            "SIGNAL": 0
        }
        self._pending_exits: Dict[str, str] = {} # order_id -> symbol

        # Cached dependencies
        self._accounting_service = None
        self._feature_store = None

        # Load configurations
        self.config = self._load_config()
        logger.info("ExitEngineOrchestrator: initialized config=%s", self.config)

    def _load_config(self) -> ExitEngineConfig:
        def parse_pct(val_str: Optional[str]) -> Optional[float]:
            if not val_str:
                return None
            try:
                v = float(val_str)
                if v <= 0.0:
                    return None
                if v >= 1.0:
                    return v / 100.0
                return v
            except ValueError:
                return None

        def parse_float(val_str: Optional[str]) -> Optional[float]:
            if not val_str:
                return None
            try:
                return float(val_str)
            except ValueError:
                return None

        return ExitEngineConfig(
            stop_loss_pct=parse_pct(os.getenv("EXIT_STOP_LOSS_PCT")),
            take_profit_pct=parse_pct(os.getenv("EXIT_TAKE_PROFIT_PCT")),
            trailing_pct=parse_pct(os.getenv("EXIT_TRAILING_PCT")),
            break_even_trigger_pct=parse_pct(os.getenv("EXIT_BREAK_EVEN_TRIGGER")),
            time_stop_seconds=parse_float(os.getenv("EXIT_TIME_SECONDS")),
            atr_multiplier=parse_float(os.getenv("EXIT_ATR_MULTIPLIER")),
            volatility_threshold=parse_float(os.getenv("EXIT_VOLATILITY_THRESHOLD")),
            risk_score_threshold=parse_float(os.getenv("EXIT_RISK_SCORE_THRESHOLD")),
        )

    def on_valuation_update(self, event: Any) -> None:
        """Handle PositionValuationUpdated (fired on every market tick)."""
        payload = getattr(event, "payload", {}) or {}
        symbol = payload.get("symbol")
        price_raw = payload.get("price")
        if not symbol or price_raw is None:
            return

        price = float(price_raw)

        with self._lock:
            if not self._accounting_service:
                if self._container.has("PortfolioAccounting"):
                    self._accounting_service = self._container.resolve("PortfolioAccounting")
                else:
                    return

            pos = self._accounting_service.valuation_engine.get_position(symbol)
            if not pos:
                # Remove active state tracking
                self._exit_states.pop(symbol, None)
                return

            state = self._exit_states.get(symbol)
            if not state:
                state = PositionExitState(symbol=symbol)
                self._exit_states[symbol] = state

            # Check if exit is already requested and pending fill
            if state.exit_requested:
                return

            # FP-4 / ADR-001: ATR for stop-loss comes from PriceActionOrchestrator (canonical).
            # normalized_atr and risk_score remain Feature Platform-owned — no PA equivalent.
            atr_val = None
            norm_atr_val = None
            risk_score_val = None

            # 1. PA-ATR — canonical external ATR for risk decisions (ADR-001)
            try:
                if self._container and self._container.has("PriceActionOrchestrator"):
                    pa_orch = self._container.resolve("PriceActionOrchestrator")
                    pa_atr = pa_orch.get_atr(symbol)
                    if pa_atr > 0.0:
                        atr_val = pa_atr
            except Exception as e:
                logger.debug("ExitEngine: error resolving PriceActionOrchestrator for ATR: %s", e)

            # 2. Feature Platform — normalized_atr and risk_score (internal FP values, no PA equivalent)
            try:
                if self._container and self._container.has("FeaturePlatformOrchestrator"):
                    fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
                    df_feat = fp_orch.query_realtime(["normalized_atr", "risk_score"], [symbol])
                    if df_feat is not None and not df_feat.empty:
                        row = df_feat.iloc[-1]
                        norm_atr_val = row.get("normalized_atr")
                        risk_score_val = row.get("risk_score")
            except Exception as e:
                logger.debug("ExitEngine: error querying features via query_realtime: %s", e)

            # Initialize initial ATR stop if configured
            if state.initial_atr_stop is None and self.config.atr_multiplier is not None and atr_val is not None:
                dist = self.config.atr_multiplier * atr_val
                if pos.side == "LONG":
                    state.initial_atr_stop = pos.average_entry - dist
                else:
                    state.initial_atr_stop = pos.average_entry + dist

            # 1. Check Stop Loss (Percentage-based)
            if self.config.stop_loss_pct is not None:
                sl_pct = self.config.stop_loss_pct
                if pos.side == "LONG":
                    sl_level = pos.average_entry * (1.0 - sl_pct)
                    if price <= sl_level:
                        self._trigger_exit(pos, price, "STOP_LOSS", f"Stop Loss breached at {price} <= {sl_level:.4f}")
                        return
                else:
                    sl_level = pos.average_entry * (1.0 + sl_pct)
                    if price >= sl_level:
                        self._trigger_exit(pos, price, "STOP_LOSS", f"Stop Loss breached at {price} >= {sl_level:.4f}")
                        return

            # 2. Check ATR Stop
            if state.initial_atr_stop is not None:
                atr_stop = state.initial_atr_stop
                if pos.side == "LONG":
                    if price <= atr_stop:
                        self._trigger_exit(pos, price, "ATR_STOP", f"ATR Stop breached at {price} <= {atr_stop:.4f}")
                        return
                else:
                    if price >= atr_stop:
                        self._trigger_exit(pos, price, "ATR_STOP", f"ATR Stop breached at {price} >= {atr_stop:.4f}")
                        return

            # 3. Check Take Profit
            if self.config.take_profit_pct is not None:
                tp_pct = self.config.take_profit_pct
                if pos.side == "LONG":
                    tp_level = pos.average_entry * (1.0 + tp_pct)
                    if price >= tp_level:
                        self._trigger_exit(pos, price, "TAKE_PROFIT", f"Take Profit reached at {price} >= {tp_level:.4f}")
                        return
                else:
                    tp_level = pos.average_entry * (1.0 - tp_pct)
                    if price <= tp_level:
                        self._trigger_exit(pos, price, "TAKE_PROFIT", f"Take Profit reached at {price} <= {tp_level:.4f}")
                        return

            # 4. Check Trailing Stop
            if self.config.trailing_pct is not None:
                trail_pct = self.config.trailing_pct
                if pos.side == "LONG":
                    watermark = pos.highest_price_seen
                    stop_level = watermark * (1.0 - trail_pct)
                    state.trailing_stop_level = stop_level
                    if price <= stop_level:
                        self._trigger_exit(pos, price, "TRAILING_STOP", f"Trailing Stop breached at {price} <= {stop_level:.4f} (watermark {watermark})")
                        return
                else:
                    watermark = pos.lowest_price_seen
                    stop_level = watermark * (1.0 + trail_pct)
                    state.trailing_stop_level = stop_level
                    if price >= stop_level:
                        self._trigger_exit(pos, price, "TRAILING_STOP", f"Trailing Stop breached at {price} >= {stop_level:.4f} (watermark {watermark})")
                        return

            # 5. Check Break Even
            if self.config.break_even_trigger_pct is not None:
                be_trigger = self.config.break_even_trigger_pct
                if pos.pnl_percent >= be_trigger * 100.0:
                    state.break_even_activated = True

                if state.break_even_activated:
                    if pos.side == "LONG":
                        if price <= pos.average_entry:
                            self._trigger_exit(pos, price, "BREAK_EVEN", f"Break Even triggered at {price} <= average entry {pos.average_entry}")
                            return
                    else:
                        if price >= pos.average_entry:
                            self._trigger_exit(pos, price, "BREAK_EVEN", f"Break Even triggered at {price} >= average entry {pos.average_entry}")
                            return

            # 6. Check Time Stop
            if self.config.time_stop_seconds is not None:
                held_seconds = (datetime.now(timezone.utc) - pos.opened_at).total_seconds()
                if held_seconds > self.config.time_stop_seconds:
                    self._trigger_exit(pos, price, "TIME_STOP", f"Max hold duration reached: {held_seconds:.1f}s > {self.config.time_stop_seconds}s")
                    return

            # 7. Check Volatility Exit
            if self.config.volatility_threshold is not None and norm_atr_val is not None:
                if norm_atr_val > self.config.volatility_threshold:
                    self._trigger_exit(pos, price, "VOLATILITY", f"Volatility threshold breached: norm_atr {norm_atr_val:.4f} > {self.config.volatility_threshold}")
                    return
            if self.config.risk_score_threshold is not None and risk_score_val is not None:
                if risk_score_val > self.config.risk_score_threshold:
                    self._trigger_exit(pos, price, "VOLATILITY", f"Risk score threshold breached: risk_score {risk_score_val:.2f} > {self.config.risk_score_threshold}")
                    return

    def _trigger_exit(self, position: Any, exit_price: float, reason: str, rationale: str) -> None:
        symbol = position.symbol
        state = self._exit_states[symbol]
        state.exit_requested = True
        state.exit_reason = reason

        # Publish triggered events
        if reason == "STOP_LOSS":
            from research_platform.exit_engine.events import StopLossTriggered
            self._event_bus.publish(StopLossTriggered(payload={"symbol": symbol, "price": exit_price, "stop_price": exit_price}))
        elif reason == "TAKE_PROFIT":
            from research_platform.exit_engine.events import TakeProfitTriggered
            self._event_bus.publish(TakeProfitTriggered(payload={"symbol": symbol, "price": exit_price, "target_price": exit_price}))
        elif reason == "TRAILING_STOP":
            from research_platform.exit_engine.events import TrailingStopUpdated
            self._event_bus.publish(TrailingStopUpdated(payload={"symbol": symbol, "new_stop_price": exit_price}))

        # Publish PositionExitRequested
        from research_platform.exit_engine.events import PositionExitRequested
        self._event_bus.publish(PositionExitRequested(payload={
            "symbol": symbol,
            "direction": "SELL" if position.side == "LONG" else "BUY",
            "quantity": position.quantity,
            "exit_price": exit_price,
            "reason": reason,
            "rationale": rationale
        }))

        # Resolve TradeManager
        trade_manager = None
        if self._container.has("TradeManager"):
            trade_manager = self._container.resolve("TradeManager")
        else:
            for k in [LiveTradingOrchestrator, "LiveTradingOrchestrator"]:
                if self._container.has(k):
                    live_orch = self._container.resolve(k)
                    trade_manager = getattr(live_orch, "_trade_manager", None)
                    if trade_manager:
                        break

        if trade_manager:
            order_id = f"exit_{uuid.uuid4().hex[:8]}"
            logger.info("ExitEngine: submitting exit order %s for %s side=%s qty=%.4f reason=%s",
                        order_id, symbol, position.side, position.quantity, reason)
            
            self._pending_exits[order_id] = symbol

            success = trade_manager.execute_signal_trade(
                order_id=order_id,
                symbol=symbol,
                direction="SELL" if position.side == "LONG" else "BUY",
                quantity=position.quantity,
                price=exit_price
            )
            if not success:
                logger.error("ExitEngine: exit order %s submission failed", order_id)
                state.exit_requested = False
                state.exit_reason = None
                self._pending_exits.pop(order_id, None)
                from research_platform.exit_engine.events import ExitRejected
                self._event_bus.publish(ExitRejected(payload={"symbol": symbol, "order_id": order_id, "error_message": "Submission failed"}))
        else:
            logger.error("ExitEngine: TradeManager not resolved from container. Cannot execute exit.")
            state.exit_requested = False
            state.exit_reason = None

    def on_trade_closed(self, event: Any) -> None:
        """Handle system.trade_closed event from accounting service."""
        payload = getattr(event, "payload", {}) or {}
        symbol = payload.get("symbol")
        if not symbol:
            return

        with self._lock:
            state = self._exit_states.pop(symbol, None)
            reason = "SIGNAL"
            if state and state.exit_requested:
                reason = state.exit_reason or "EXIT"

            # Increment count
            self._exit_counts[reason] = self._exit_counts.get(reason, 0) + 1

            # Remove from pending exits
            pending_keys = [k for k, v in self._pending_exits.items() if v == symbol]
            for pk in pending_keys:
                self._pending_exits.pop(pk, None)

            # Retrieve details from TradeJournal
            holding_time = 0.0
            entry_price = 0.0
            exit_price = 0.0
            realized_pnl = payload.get("realized_pnl", 0.0)
            net_pnl = payload.get("net_pnl", 0.0)
            return_pct = payload.get("return_pct", 0.0)

            if self._accounting_service:
                records = self._accounting_service.trade_journal.get_all()
                if records:
                    matching = [r for r in records if r.symbol == symbol]
                    if matching:
                        latest_record = matching[-1]
                        holding_time = latest_record.holding_duration_seconds
                        entry_price = latest_record.entry_price
                        exit_price = latest_record.exit_price
                        realized_pnl = latest_record.realized_pnl
                        return_pct = latest_record.return_pct

            # Save in history of triggered exits
            trigger_record = {
                "symbol": symbol,
                "exit_price": exit_price,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "realized_pnl": realized_pnl
            }
            self._triggered_stops.append(trigger_record)

            # Publish PositionClosed
            from research_platform.exit_engine.events import PositionClosed
            self._event_bus.publish(PositionClosed(payload={
                "symbol": symbol,
                "exit_reason": reason,
                "holding_time_seconds": holding_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "realized_pnl": realized_pnl,
                "return_pct": return_pct
            }))

    def get_summary(self) -> dict:
        """Return exit engine metrics and tracked states for the runtime API."""
        with self._lock:
            winning_count = 0
            losing_count = 0
            open_positions_list = []

            if self._accounting_service:
                positions = self._accounting_service.valuation_engine.get_all_positions()
                for p in positions:
                    if p.unrealized_pnl > 0:
                        winning_count += 1
                    elif p.unrealized_pnl < 0:
                        losing_count += 1
                    
                    open_positions_list.append({
                        "symbol": p.symbol,
                        "side": p.side,
                        "quantity": p.quantity,
                        "average_entry": p.average_entry,
                        "current_price": p.current_price,
                        "unrealized_pnl": p.unrealized_pnl
                    })

            realized_pnl = 0.0
            unrealized_pnl = 0.0
            if self._accounting_service:
                summary = self._accounting_service.get_portfolio_summary()
                realized_pnl = summary.get("realized_pnl", 0.0)
                unrealized_pnl = summary.get("unrealized_pnl", 0.0)

            avg_holding_time = 0.0
            if self._accounting_service:
                records = self._accounting_service.trade_journal.get_all()
                if records:
                    avg_holding_time = sum(r.holding_duration_seconds for r in records) / len(records)

            trailing_stops = {}
            for sym, st in self._exit_states.items():
                if st.trailing_stop_level is not None:
                    trailing_stops[sym] = st.trailing_stop_level

            return {
                "open_positions": open_positions_list,
                "pending_exits": list(self._pending_exits.values()),
                "triggered_stops": self._triggered_stops,
                "trailing_stops": trailing_stops,
                "winning_positions": winning_count,
                "losing_positions": losing_count,
                "average_holding_time": avg_holding_time,
                "exit_counts": dict(self._exit_counts),
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl
            }

    def on_order_rejected(self, event: Any) -> None:
        """Handle system.order_rejected event."""
        payload = getattr(event, "payload", {}) or {}
        order_id = payload.get("order_id")
        reason = payload.get("reason", "Rejected by validation")
        if not order_id or order_id not in self._pending_exits:
            return

        with self._lock:
            symbol = self._pending_exits.pop(order_id, None)
            if symbol:
                state = self._exit_states.get(symbol)
                if state:
                    state.exit_requested = False
                    state.exit_reason = None
                logger.warning("ExitEngine: exit order %s for %s was REJECTED: %s. Resetting exit requested flag.",
                               order_id, symbol, reason)
                try:
                    from research_platform.exit_engine.events import ExitRejected
                    self._event_bus.publish(ExitRejected(payload={
                        "symbol": symbol,
                        "order_id": order_id,
                        "error_message": f"Order rejected: {reason}"
                    }))
                except Exception:
                    pass

    def on_order_state_changed(self, event: Any) -> None:
        """Handle system.oms_order_state_changed event."""
        payload = getattr(event, "payload", {}) or {}
        order_id = payload.get("order_id")
        status = payload.get("status")
        if not order_id or not status or order_id not in self._pending_exits:
            return

        if status in ("REJECTED", "CANCELLED", "EXPIRED"):
            with self._lock:
                symbol = self._pending_exits.pop(order_id, None)
                if symbol:
                    state = self._exit_states.get(symbol)
                    if state:
                        state.exit_requested = False
                        state.exit_reason = None
                    logger.warning("ExitEngine: exit order %s for %s changed to terminal failure state %s. Resetting exit requested flag.",
                                   order_id, symbol, status)
                    try:
                        from research_platform.exit_engine.events import ExitRejected
                        self._event_bus.publish(ExitRejected(payload={
                            "symbol": symbol,
                            "order_id": order_id,
                            "error_message": f"Order transitioned to terminal status {status}"
                        }))
                    except Exception:
                        pass

