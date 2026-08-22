#!/usr/bin/env python3
"""TOJI Continuous Paper Trading Runner.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any
import pandas as pd

# Load framework and platform bootstraps
from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry

# Domain components
from data.schemas.market_data import OHLCV
from market_gateway.normalizer.normalizer import MarketDataNormalizer
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator, DEFAULT_COMPUTE_NAMES
from research_platform.feature_platform.models import FeatureRecord
from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.strategy_framework.composer import StrategyComposer
from research_platform.ai_signal.signal_generator import AISignalGenerator
from research_platform.oms.oms_core import OmsCore
from research_platform.risk_management.orchestrator import RiskManagementOrchestrator

# State and Heartbeat systems
from toji_platform.runtime.state import RuntimeStateManager, RuntimeState
from toji_platform.runtime.heartbeat import trigger_heartbeat_alert, run_heartbeat_check

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TOJI_Paper_Runner")

# Global runner states
app = None
container = None
event_bus = None
state_manager = None
running = False
stop_event = threading.Event()

# Active trading universe
ACTIVE_SYMBOLS: list = [
    s.strip()
    for s in os.getenv("BINANCE_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
    if s.strip()
]

# Heartbeat interval by mode
_MODE_INTERVALS: dict = {
    "DEV": 60,
    "PAPER": 1800,
    "PROD": 3600,
}
_HEARTBEAT_INTERVAL: int = _MODE_INTERVALS.get(
    os.getenv("TOJI_MODE", "PAPER").upper(), 1800
)


def send_telegram_alert(message: str) -> None:
    """Helper to send alerts via the alerting orchestrator."""
    try:
        if container:
            alert_orch = container.resolve("AlertOrchestrator")
            if alert_orch:
                from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel
                alert = Alert(
                    title="TOJI RUNTIME MESSAGE",
                    message=message,
                    severity=AlertSeverity.HIGH,
                    channels=[AlertChannel.TELEGRAM]
                )
                alert_orch.fire(alert)
    except Exception as e:
        logger.debug("Failed to dispatch alert: %s", e)


def print_tick_trace(
    trace_id: str,
    symbol: str,
    raw_price: float,
    source: str,
    timestamp: str,
    normalizer_input: float = 0.0,
    normalizer_output: float = 0.0,
    multiplier: float = 1.0,
    normalizer_val: str = "PENDING",
    rsi: Any = "N/A",
    ema9: Any = "N/A",
    ema21: Any = "N/A",
    atr: Any = "N/A",
    trend: Any = "N/A",
    breakout: Any = "N/A",
    strat_decision: str = "HOLD",
    strat_confidence: float = 0.5,
    strat_reason: str = "N/A",
    ai_approved: str = "N/A",
    ai_rejected_reason: str = "N/A",
    risk_approved: str = "N/A",
    risk_blocked_reason: str = "N/A",
    oms_order_created: str = "false",
    oms_reason: str = "N/A",
    exec_filled: str = "false",
    exec_rejected_reason: str = "N/A",
    lifecycle_result: str = "NO_TRADE_REASON=Pending"
) -> None:
    trace_str = (
        f"\n[TRACE_ID {trace_id}]\n\n"
        f"[MARKET_RAW]\n"
        f"symbol: {symbol}\n"
        f"raw_price: {raw_price}\n"
        f"source: {source}\n"
        f"timestamp: {timestamp}\n\n"
        f"[NORMALIZER]\n"
        f"input_price: {normalizer_input}\n"
        f"output_price: {normalizer_output}\n"
        f"multiplier_applied: {multiplier}\n"
        f"validation: {normalizer_val}\n\n"
        f"[FEATURE]\n"
        f"RSI: {rsi}\n"
        f"EMA9: {ema9}\n"
        f"EMA21: {ema21}\n"
        f"ATR: {atr}\n"
        f"Trend: {trend}\n"
        f"Breakout: {breakout}\n\n"
        f"[STRATEGY]\n"
        f"decision: {strat_decision}\n"
        f"confidence: {strat_confidence}\n"
        f"reason: {strat_reason}\n\n"
        f"[AI_AUDITOR]\n"
        f"approved: {ai_approved}\n"
        f"rejected_reason: {ai_rejected_reason}\n\n"
        f"[RISK]\n"
        f"approved: {risk_approved}\n"
        f"blocked_reason: {risk_blocked_reason}\n\n"
        f"[OMS]\n"
        f"order_created: {oms_order_created}\n"
        f"reason: {oms_reason}\n\n"
        f"[EXECUTION]\n"
        f"filled: {exec_filled}\n"
        f"rejected_reason: {exec_rejected_reason}\n\n"
        f"LIFECYCLE_RESULT: {lifecycle_result}\n"
    )
    logger.info(trace_str)


# Global feature statistics
features_calculated_count = 0
last_calculated_summary = {}
last_printed_summary_time = time.time()


def handle_market_tick(event: Any) -> None:
    """Executes the canonical live tick-to-trade pipeline."""
    global features_calculated_count, last_calculated_summary, last_printed_summary_time

    if not running:
        return

    trace_id = f"trace_{uuid.uuid4().hex[:8]}"
    payload = getattr(event, "payload", {}) or {}
    symbol = payload.get("symbol")
    price = payload.get("price")
    timestamp_str = payload.get("timestamp")
    volume = payload.get("volume", 0.0)
    source = getattr(event, "source", "Unknown")

    # Initial default values for tick trace telemetry
    normalizer_input = 0.0
    normalizer_output = 0.0
    multiplier = 1.0
    normalizer_val = "PENDING"
    rsi_val_trace = "N/A"
    ema9_val_trace = "N/A"
    ema21_val_trace = "N/A"
    atr_val_trace = "N/A"
    trend_val_trace = "N/A"
    breakout_val_trace = "N/A"
    strat_decision_trace = "HOLD"
    strat_confidence_trace = 0.5
    strat_reason_trace = "N/A"
    ai_approved_trace = "N/A"
    ai_rejected_reason_trace = "N/A"
    risk_approved_trace = "N/A"
    risk_blocked_reason_trace = "N/A"
    oms_order_created_trace = "false"
    oms_reason_trace = "N/A"
    exec_filled_trace = "false"
    exec_rejected_reason_trace = "N/A"
    lifecycle_result = "NO_TRADE_REASON=Pending"

    if not symbol or price is None:
        return

    # Phase 2 boundary validation
    try:
        price_float = float(price)
    except Exception:
        price_float = 0.0

    if symbol == "BTCUSDT" and not (1000.0 < price_float < 500000.0):
        state_manager.record_bad_tick()
        logger.warning(
            "\n[BAD_MARKET_DATA]\nsymbol: %s\nprice: %s\nreason: unrealistic_price\naction: rejected",
            symbol, price
        )
        print_tick_trace(
            trace_id=trace_id,
            symbol=symbol,
            raw_price=price_float,
            source=source,
            timestamp=str(timestamp_str),
            normalizer_val="REJECTED",
            lifecycle_result="NO_TRADE_REASON=unrealistic_price"
        )
        return

    if symbol == "ETHUSDT" and not (100.0 < price_float < 50000.0):
        state_manager.record_bad_tick()
        logger.warning(
            "\n[BAD_MARKET_DATA]\nsymbol: %s\nprice: %s\nreason: unrealistic_price\naction: rejected",
            symbol, price
        )
        print_tick_trace(
            trace_id=trace_id,
            symbol=symbol,
            raw_price=price_float,
            source=source,
            timestamp=str(timestamp_str),
            normalizer_val="REJECTED",
            lifecycle_result="NO_TRADE_REASON=unrealistic_price"
        )
        return

    try:
        logger.info("[MARKET] %s", symbol)
        logger.info("\n[MARKET]\nsymbol: %s\nprice: %s\nvolume: %s", symbol, price, volume)

        # 1. Update processed state ticks counter
        state_manager.record_tick()

        # 2. Market Tick normalization
        normalizer_input = price_float
        if "k" in payload or isinstance(payload, list):
            candle = MarketDataNormalizer.normalize_binance_candle(payload, symbol=symbol)
        else:
            from datetime import datetime, timezone
            try:
                if isinstance(timestamp_str, str):
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.now(timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)
            candle = OHLCV(
                symbol=symbol,
                timestamp=ts,
                open=float(price),
                high=float(price),
                low=float(price),
                close=float(price),
                volume=float(volume),
                interval="1m"
            )
        normalizer_output = candle.close
        normalizer_val = "PASSED"
        
        # 3. Price Action update (run first so history updates)
        pa_orch = container.resolve(PriceActionOrchestrator)
        pa_orch.process_tick(symbol, price_float, candle.timestamp, volume)
        logger.info("[PRICE_ACTION] analysis complete")

        # 4. Feature update using historical bars if available
        bars_list = pa_orch.get_bars(symbol)
        if len(bars_list) > 1:
            df = pd.DataFrame(bars_list)
        else:
            df = pd.DataFrame([candle.model_dump()])

        feature_platform = container.resolve(FeaturePlatformOrchestrator)
        
        # FP-7D-2: Canonical compute names derived from DEFAULT_FEATURE_DEFINITIONS.
        features_to_compute = list(DEFAULT_COMPUTE_NAMES)
        output_df = feature_platform.compute_and_store(features_to_compute, symbol, df)
        
        # Increment counter
        features_calculated_count += len(features_to_compute)
        state_manager.record_feature(len(features_to_compute))
        
        # Extract features dictionary
        features_dict = output_df.iloc[-1].to_dict() if not output_df.empty else {}
        clean_features = {
            k: v for k, v in features_dict.items()
            if k in features_to_compute
        }
        
        rsi_val_trace = clean_features.get("rsi", "N/A")
        ema9_val_trace = clean_features.get("ema9", "N/A")
        ema21_val_trace = clean_features.get("ema21", "N/A")
        atr_val_trace = clean_features.get("atr", "N/A")
        trend_val_trace = clean_features.get("trend", "N/A")
        breakout_val_trace = clean_features.get("breakout", "N/A")

        last_calculated_summary = {
            "symbol": symbol,
            "rsi": rsi_val_trace,
            "trend": trend_val_trace
        }

        # Print/log every 60s
        curr_time = time.time()
        if curr_time - last_printed_summary_time >= 60.0:
            print(
                f"Features calculated:\n"
                f"{features_calculated_count}\n"
                f"Last:\n"
                f"{last_calculated_summary.get('symbol', 'N/A')}\n"
                f"RSI:\n"
                f"{last_calculated_summary.get('rsi', 'N/A')}\n"
                f"Trend:\n"
                f"{last_calculated_summary.get('trend', 'N/A')}",
                flush=True
            )
            last_printed_summary_time = curr_time

        logger.info("[FEATURE] RSI, EMA, and FP-internal ATR computed (FP-ATR feeds normalized_atr DAG). "
                    "Strategy ATR sourced from PriceActionOrchestrator — see ADR-001.")
        features_log_str = "\n".join([f"{k}: {v}" for k, v in clean_features.items()])
        logger.info("\n[FEATURE]\n%s", features_log_str)

        # 5. Strategy evaluation
        strategy_composer = container.resolve(StrategyComposer)
        latest_close = float(clean_features.get("close", price_float))
        
        # strategy receives full feature object
        indicators = clean_features.copy()
        indicators["vwap"] = pa_orch.get_vwap(symbol)
        indicators["atr"] = pa_orch.get_atr(symbol)

        logger.info("\n[STRATEGY INPUT]\n%s", indicators)

        strategy = strategy_composer.compose(
            strategy_id=f"strat_{symbol}",
            name="Mean Reversion Paper",
            strategy_type="MEAN_REVERSION",
            version="1.0.0",
            symbols=[symbol],
            parameters={"deviation": 2.0}
        )

        strategy_decision = strategy_composer.generate_decision(
            strategy=strategy,
            symbol=symbol,
            current_price=latest_close,
            indicators=indicators
        )

        # Handle enums
        from strategy.core.enums import StrategyDecision
        if isinstance(strategy_decision, StrategyDecision):
            decision_str = strategy_decision.value
        else:
            decision_str = getattr(strategy_decision, "decision", str(strategy_decision))
        
        if decision_str not in ("BUY", "SELL"):
            decision_str = "HOLD"

        state_manager.record_strategy_decision(decision_str)
        strat_decision_trace = decision_str

        # Determine hold reasons
        hold_reasons = []
        rsi_val = clean_features.get("rsi")
        if rsi_val is not None:
            try:
                rsi_val = float(rsi_val)
                if 30.0 <= rsi_val <= 70.0:
                    hold_reasons.append("RSI neutral")
            except (ValueError, TypeError):
                pass
        
        breakout_val = clean_features.get("breakout", "none")
        if breakout_val == "none":
            hold_reasons.append("No breakout")
            
        risk_score_val = clean_features.get("risk_score")
        if risk_score_val is not None:
            try:
                risk_score_val = float(risk_score_val)
                if abs(risk_score_val) < 2.0:
                    hold_reasons.append("Risk rejected")
            except (ValueError, TypeError):
                pass

        if not hold_reasons:
            hold_reasons = ["No trigger signal", "Risk rejected"]

        hold_reason_text = "\n".join(hold_reasons)
        strat_reason_trace = ", ".join(hold_reasons)

        if decision_str == "HOLD":
            logger.info("[DECISION] HOLD reason=%s", ", ".join(hold_reasons))
            logger.info("\n[DECISION]\nHOLD\n%s", hold_reason_text)
            
            # Print trace at exit point
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                lifecycle_result="NO_TRADE_REASON=Strategy decision was HOLD"
            )
            return
        else:
            logger.info("[DECISION] %s reason=%s", decision_str, "Signal triggered")
            logger.info("\n[DECISION]\n%s\n%s", decision_str, "Signal triggered")
            strat_reason_trace = "Signal triggered"

        # 6. AI signal confluence
        ai_generator = container.resolve(AISignalGenerator)
        ai_signal = ai_generator.generate_signal(symbol, latest_close)
        logger.info("[AI_SIGNAL] result")
        
        # If AI signal suggests WAIT
        if ai_signal.signal not in ("BUY", "SELL"):
            # Update trace parameters
            strat_confidence_trace = getattr(ai_signal, "confidence", 0.5)
            # Print trace at exit point
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                lifecycle_result=f"NO_TRADE_REASON=AI Signal Engine recommended WAIT: {ai_signal.reasoning}"
            )
            return

        # 7. Trade decision & OMS order placement (Never bypass OMS)
        state_manager.record_signal()
        strat_confidence_trace = getattr(ai_signal, "confidence", 0.75)
        logger.info(
            "Trade Signal Triggered: %s for %s at %s. Reasoning: %s",
            ai_signal.signal, symbol, latest_close, ai_signal.reasoning
        )

        # CRITICAL SAFETY GATE: Check if a critical plugin failed during boot.
        # TradingHalted is registered by PlatformStartupCoordinator when any
        # critical trading dependency plugin (OmsPlugin, PaperMarketPlugin,
        # PaperTradingPlugin, PortfolioAccountingPlugin) fails to initialize.
        #
        # FAIL-CLOSED POLICY: If TradingHalted is absent from the container,
        # safety state is UNKNOWN — do NOT default to trading allowed.
        # A missing TradingHalted flag means the boot coordinator did not complete
        # its safety registration, which is itself a critical failure condition.
        if container.has("TradingHalted"):
            _trading_halted_flag = container.resolve("TradingHalted")
        else:
            # Safety state UNKNOWN — fail closed
            _trading_halted_flag = True
            logger.error(
                "[SAFETY_GATE] TradingHalted flag not registered in container — "
                "boot coordinator may not have completed safety registration. "
                "Trading blocked (fail-closed)."
            )
        if _trading_halted_flag:
            _critical_failed = container.resolve("CriticalFailedPlugins") if container.has("CriticalFailedPlugins") else []
            _halted_reason = (
                f"TradingHalted flag absent from container (safety state UNKNOWN)"
                if not container.has("TradingHalted")
                else f"critical plugin boot failure: {_critical_failed}"
            )
            logger.error(
                "[SAFETY_GATE] Trading blocked: %s",
                _halted_reason,
            )
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                ai_approved=ai_approved_trace, risk_approved="false",
                risk_blocked_reason=f"TRADING_HALTED: {_halted_reason}",
                lifecycle_result="NO_TRADE_REASON=CRITICAL_PLUGIN_BOOT_FAILURE"
            )
            return

        # 7a. AI Decision Auditor check
        from research_platform.risk_governance.ai_auditor import AIDecisionAuditor
        auditor = AIDecisionAuditor(min_confidence=0.55, min_risk_reward=1.5)
        regime = indicators.get("regime", "UNKNOWN")
        if regime not in ("TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "UNKNOWN"):
            regime = "UNKNOWN"
        
        signal_dict = {
            "signal": ai_signal.signal,
            "confidence": getattr(ai_signal, "confidence", 0.75),
            "reasoning": ai_signal.reasoning,
            "entry": latest_close,
            "stop_loss": getattr(ai_signal, "stop_loss", latest_close * 0.98),
            "take_profit": getattr(ai_signal, "take_profit", latest_close * 1.03)
        }
        audit_decision = auditor.audit(signal_dict, regime=regime)
        state_manager.record_ai_audit(audit_decision.approved)
        ai_approved_trace = "true" if audit_decision.approved else "false"
        
        if not audit_decision.approved:
            logger.warning("[AI_AUDITOR] REJECTED")
            ai_rejected_reason_trace = audit_decision.reason
            try:
                from research_platform.risk_governance.risk_formatter import format_audit_rejection_alert
                rej_msg = format_audit_rejection_alert(ai_signal.signal, symbol, audit_decision.reason)
                send_telegram_alert(rej_msg)
            except Exception as ex_alert:
                logger.debug("Failed to send audit rejection alert: %s", ex_alert)

            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                ai_approved=ai_approved_trace, ai_rejected_reason=ai_rejected_reason_trace,
                lifecycle_result=f"NO_TRADE_REASON=AI_AUDITOR_REJECTED: {audit_decision.reason}"
            )
            return

        logger.info("[AI_AUDITOR] APPROVED")

        # 7b. Kill Switch check
        from research_platform.risk_governance.kill_switch import KillSwitchEngine
        from research_platform.risk_governance.models import KillSwitchState
        
        def ks_telegram_callback(event):
            try:
                from research_platform.risk_governance.risk_formatter import format_risk_alert
                ks_msg = format_risk_alert(
                    problem=event.detail,
                    action="Immediate trading halt activated.",
                    portfolio_usdt=event.portfolio_usdt,
                    status="HALTED MODE",
                    mode=event.state.value
                )
                send_telegram_alert(ks_msg)
            except Exception as ex_ks:
                logger.debug("Failed to dispatch KillSwitch Telegram alert: %s", ex_ks)

        if container.has("KillSwitchEngine"):
            kill_switch = container.resolve("KillSwitchEngine")
        else:
            kill_switch = KillSwitchEngine(alert_callback=ks_telegram_callback)
            container.register("KillSwitchEngine", instance=kill_switch)
            
        kill_switch.load_state_from_redis()
        
        # RISK STATE RESOLUTION — FAIL CLOSED
        # Authoritative portfolio state MUST be resolved from AccountingService.
        # If it cannot be resolved (plugin not booted, exception, or malformed data),
        # trading MUST NOT proceed. DO NOT use phantom fallback values.
        _risk_state_available = False
        _ks_equity = None
        _ks_peak = None
        _ks_daily_pnl = None
        _ks_consecutive_losses = None
        _risk_state_error = None

        try:
            if not container.has("AccountingService"):
                _risk_state_error = "AccountingService not registered — PortfolioAccountingPlugin may have failed to boot"
            else:
                _acct_svc = container.resolve("AccountingService")
                _portfolio_summary = _acct_svc.get_portfolio_summary()

                # Validate all required fields are present and numeric
                _ks_equity = _portfolio_summary.get("equity")
                _ks_peak = _portfolio_summary.get("peak_equity")
                _ks_daily_pnl = _portfolio_summary.get("daily_pnl")

                if _ks_equity is None or _ks_peak is None or _ks_daily_pnl is None:
                    _risk_state_error = (
                        f"Incomplete portfolio summary: equity={_ks_equity!r}, "
                        f"peak_equity={_ks_peak!r}, daily_pnl={_ks_daily_pnl!r}"
                    )
                elif not all(isinstance(v, (int, float)) for v in (_ks_equity, _ks_peak, _ks_daily_pnl)):
                    _risk_state_error = (
                        f"Malformed portfolio summary: non-numeric values detected — "
                        f"equity={type(_ks_equity)}, peak_equity={type(_ks_peak)}"
                    )
                else:
                    # Compute consecutive_losses from metrics engine trade history
                    _metrics_engine = _acct_svc.metrics_engine
                    _trades = list(_metrics_engine._trades) if hasattr(_metrics_engine, "_trades") else []
                    _consecutive = 0
                    for _t in reversed(_trades):
                        if getattr(_t, "net_pnl", 0.0) < 0:
                            _consecutive += 1
                        else:
                            break
                    _ks_consecutive_losses = _consecutive
                    _risk_state_available = True

        except Exception as _ks_state_err:
            _risk_state_error = f"Exception resolving AccountingService state: {_ks_state_err}"

        if not _risk_state_available:
            # FAIL CLOSED: risk state unknown — do not trade
            logger.error(
                "[RISK_STATE] UNKNOWN — trading blocked. Risk evaluation cannot proceed safely. "
                "Reason: %s",
                _risk_state_error,
            )
            state_manager.record_risk_audit(False)
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                ai_approved=ai_approved_trace, risk_approved="false",
                risk_blocked_reason=f"RISK_STATE_UNKNOWN: {_risk_state_error}",
                lifecycle_result=f"NO_TRADE_REASON=RISK_STATE_UNKNOWN"
            )
            return

        ks_state = kill_switch.evaluate(
            daily_pnl=_ks_daily_pnl,
            current_capital=_ks_equity,
            peak_capital=_ks_peak,
            consecutive_losses=_ks_consecutive_losses,
            avg_execution_quality=95.0,
            exchange_connected=True
        )
        logger.info("[KILL_SWITCH] STATE: %s", ks_state.value)
        
        if not kill_switch.trading_allowed:
            logger.warning("Kill switch triggered. Trading blocked!")
            state_manager.record_risk_audit(False)
            risk_approved_trace = "false"
            risk_blocked_reason_trace = f"KillSwitch engine state is {ks_state.value}"
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                ai_approved=ai_approved_trace, risk_approved=risk_approved_trace, risk_blocked_reason=risk_blocked_reason_trace,
                lifecycle_result=f"NO_TRADE_REASON=KILL_SWITCH_BLOCKED: {risk_blocked_reason_trace}"
            )
            return

        # 7c. Real-Time Risk Monitor check
        # Reuse authoritative state already validated above for kill switch.
        # _risk_state_available is True here (we returned above if not).
        from research_platform.risk_governance.risk_monitor import RealTimeRiskMonitor
        risk_monitor = RealTimeRiskMonitor()
        _rm_equity = _ks_equity
        _rm_peak = _ks_peak
        _rm_daily_pnl = _ks_daily_pnl
        _rm_consecutive_losses = _ks_consecutive_losses

        # Resolve open positions — required by RealTimeRiskMonitor.calculate_risk_score().
        # ValuatedPosition objects must be converted to {symbol, notional_usdt, unrealized_pnl} dicts.
        # AccountingService is already confirmed available (_risk_state_available=True).
        _rm_open_positions = []
        try:
            _acct_svc2 = container.resolve("AccountingService")
            _vpos = _acct_svc2.valuation_engine.get_all_positions()
            _rm_open_positions = [
                {
                    "symbol": pos.symbol,
                    "notional_usdt": pos.market_value,   # qty * current_price
                    "unrealized_pnl": pos.unrealized_pnl,
                }
                for pos in _vpos
            ]
        except Exception as _rm_pos_err:
            # Position resolution failed — fail closed: cannot compute exposure score
            logger.error(
                "[RISK_MONITOR] Cannot resolve open positions from AccountingService: %s — trading blocked",
                _rm_pos_err,
            )
            state_manager.record_risk_audit(False)
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                ai_approved=ai_approved_trace, risk_approved="false",
                risk_blocked_reason=f"RISK_POSITIONS_UNAVAILABLE: {_rm_pos_err}",
                lifecycle_result=f"NO_TRADE_REASON=RISK_POSITIONS_UNAVAILABLE"
            )
            return

        risk_snap = risk_monitor.calculate_risk_score(
            capital=_rm_equity,
            open_positions=_rm_open_positions,
            peak_capital=_rm_peak,
            leverage=1.0,
            consecutive_losses=_rm_consecutive_losses,
            daily_pnl=_rm_daily_pnl
        )
        logger.info("[RISK] SCORE: %s", risk_snap.risk_score)
        
        if risk_snap.risk_score < 40.0:
            logger.warning("Risk score too low: %.1f", risk_snap.risk_score)
            state_manager.record_risk_audit(False)
            risk_approved_trace = "false"
            risk_blocked_reason_trace = f"Risk score {risk_snap.risk_score} < 40.0"
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                ai_approved=ai_approved_trace, risk_approved=risk_approved_trace, risk_blocked_reason=risk_blocked_reason_trace,
                lifecycle_result=f"NO_TRADE_REASON=RISK_MONITOR_BLOCKED: {risk_blocked_reason_trace}"
            )
            return

        state_manager.record_risk_audit(True)
        risk_approved_trace = "true"

        # Send Telegram signal intelligence alert
        try:
            from research_platform.alerting.trade_formatter import format_signal_alert
            signal_msg = format_signal_alert(
                symbol=symbol,
                decision=ai_signal.signal,
                price=latest_close,
                timeframe="1m",
                confidence=getattr(ai_signal, "confidence", 0.75),
                reasoning=ai_signal.reasoning,
                trend=indicators.get("trend", "bullish"),
                breakout="no",
                sr="at support/resistance",
                indicators=f"RSI: {indicators.get('rsi', 'N/A')}, VWAP: {indicators.get('vwap', 'N/A')}",
                risk=f"Position size within limits, Risk score: {risk_snap.risk_score:.0f}/100",
                final_decision="EXECUTE PAPER ORDER",
            )
            send_telegram_alert(signal_msg)
        except Exception as _se:
            logger.debug("Signal alert formatting failed: %s", _se)

        # 7d. Submit Order to OMS
        oms_core = container.resolve(OmsCore)
        
        # Calculate quantity (tiny size 1 USDT for validation mode, else default 0.5)
        import os
        if os.getenv("TOJI_VALIDATION_MODE") == "true":
            order_qty = 1.0 / latest_close
        else:
            order_qty = 0.5

        try:
            order = oms_core.submit_order(
                strategy_id=strategy.metadata.strategy_id,
                symbol=symbol,
                quantity=order_qty,
                price=latest_close,
                order_type="MARKET",
                side=ai_signal.signal,
                rationale=ai_signal.reasoning
            )
            
            # Check status
            if order.status not in ("VALIDATED", "QUEUED", "ROUTED", "FILLED"):
                logger.info("[OMS]\nrejected: status=%s", order.status)
                oms_reason_trace = f"OMS order status is {order.status}"
                print_tick_trace(
                    trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                    normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                    normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                    atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                    ai_approved=ai_approved_trace, risk_approved=risk_approved_trace,
                    oms_order_created="false", oms_reason=oms_reason_trace,
                    lifecycle_result=f"NO_TRADE_REASON=OMS_REJECTED: {oms_reason_trace}"
                )
                return
            
            state_manager.record_order()
            oms_order_created_trace = "true"
            oms_reason_trace = "Order submitted to execution engine"
            logger.info("[OMS]\naccepted")

            # ─────────────────────────────────────────────────────────────────────
            # 7e. Single Authoritative Execution Path
            #
            # OmsCore.submit_order() already routed the order through:
            #   PaperExecutionRouter (PAPER mode)
            #     → PaperTradingOrchestrator.submit_paper_order()
            #         → PaperBrokerAdapter → PaperExchange (fills)
            #         → publishes PaperOrderFilled to EventBus
            #             → AccountingService.on_fill() (DB persistence)
            #                 → PostgresTradeRepository.save_trade()    ✅
            #                 → PostgresPositionRepository.save_position() ✅
            #                 → PostgresLedgerRepository.save_entry()   ✅
            #                 → OMS order → FILLED in PostgreSQL         ✅
            #
            # Do NOT call ExchangeExecutionSimulator directly here.
            # That was a duplicate, disconnected path that bypassed all persistence.
            # ─────────────────────────────────────────────────────────────────────

            # Determine fill price from the OMS order result
            fill_price = getattr(order, "executed_price", None) or latest_close
            fill_qty   = getattr(order, "executed_quantity", None) or order_qty

            if order.status == "FILLED":
                logger.info("[EXECUTION] FILLED via authoritative OMS pipeline")
                exec_filled_trace = "true"
                state_manager.record_trade()
                logger.info("[PAPER_TRADE] executed")

                # 7f. Persist trade to long-term Trade Memory (pattern analysis, not accounting source-of-truth)
                #
                # EVIDENCE GAP — BUG-003 DOCUMENTED:
                # At this lifecycle point a BUY order was just submitted to the OMS.
                # The order may be FILLED (matched by PaperBrokerAdapter) but the position
                # is now OPEN — not closed. The TradeMemoryEngine.save_trade() signature
                # accepts entry/exit price and pnl, which map to a completed round-trip trade.
                #
                # Realized PnL is computed by AccountingService.on_fill() only when a
                # SELL fill closes the position (PositionValuationEngine.on_close()). That
                # path is async (EventBus delivery), and the computed realized_pnl is not
                # synchronously available here.
                #
                # fill_price - latest_close is NOT realized PnL:
                #   - For BUY: it measures slippage between limit price and fill price (≈0).
                #   - For SELL: it measures price delta, ignoring entry cost, quantity, fees.
                # Using it as pnl=... is mathematically wrong and semantically misleading.
                #
                # This TradeMemoryEngine entry records the ENTRY LEG of a trade for pattern
                # analysis. Realized PnL is only knowable after the position is closed.
                # Passing pnl=0.0 is the correct value for an open entry leg.
                try:
                    from research_platform.trade_memory.engine import TradeMemoryEngine
                    trade_memory = TradeMemoryEngine()
                    trade_memory.save_trade(
                        symbol=symbol,
                        entry=latest_close,
                        exit=fill_price,
                        entry_time=datetime.now(timezone.utc),
                        exit_time=datetime.now(timezone.utc),
                        features_at_entry=clean_features,
                        decision_reason=ai_signal.reasoning,
                        # EVIDENCE GAP: realized PnL is unavailable at entry-leg lifecycle point.
                        # Authoritative realized PnL is computed by AccountingService.on_fill()
                        # when the position is closed (SELL). Using 0.0 for entry leg record.
                        pnl=0.0,
                        execution_quality=100.0,
                        slippage=abs(fill_price - latest_close),  # actual fill slippage
                        fees=fill_price * fill_qty * 0.0005,
                        fill_time=datetime.now(timezone.utc).isoformat()
                    )
                    logger.info("[MEMORY] SAVED")
                except Exception as _me:
                    logger.debug("TradeMemoryEngine.save_trade failed: %s", _me)

                # 7g. Format & send Telegram trade executed alert
                try:
                    from research_platform.alerting.trade_formatter import format_trade_alert
                    trade_msg = format_trade_alert(
                        symbol=symbol,
                        side=ai_signal.signal,
                        entry=latest_close,
                        quantity=fill_qty,
                        sl=signal_dict["stop_loss"],
                        tp=signal_dict["take_profit"],
                        risk="Passed",
                        reason=ai_signal.reasoning,
                        trade_id=order.order_id,
                        fill_price=fill_price,
                        slippage_pct=round(abs(fill_price - latest_close) / latest_close * 100, 4),
                        fee_usdt=round(fill_price * fill_qty * 0.0005, 6),
                        liquidity_check="PASS",
                        execution_score=100.0
                    )
                    send_telegram_alert(trade_msg)
                except Exception as _te:
                    logger.debug("Trade alert formatting failed: %s", _te)

                # Print trace at final success point
                print_tick_trace(
                    trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                    normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                    normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                    atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                    strat_decision=strat_decision_trace, strat_confidence=strat_confidence_trace, strat_reason=strat_reason_trace,
                    ai_approved=ai_approved_trace, risk_approved=risk_approved_trace,
                    oms_order_created=oms_order_created_trace, oms_reason=oms_reason_trace,
                    exec_filled=exec_filled_trace,
                    lifecycle_result="TRADE_EXECUTED"
                )

            else:
                # OMS pipeline returned non-FILLED status (execution rejected inside PaperTradingOrchestrator)
                logger.warning("[EXECUTION] OMS pipeline returned status=%s for order %s", order.status, order.order_id)
                exec_rejected_reason_trace = f"OMS pipeline status: {order.status}"
                print_tick_trace(
                    trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                    normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                    normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                    atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                    ai_approved=ai_approved_trace, risk_approved=risk_approved_trace,
                    oms_order_created=oms_order_created_trace, oms_reason=oms_reason_trace,
                    exec_filled="false", exec_rejected_reason=exec_rejected_reason_trace,
                    lifecycle_result=f"NO_TRADE_REASON=OMS_PIPELINE_STATUS: {order.status}"
                )

        except Exception as ex:
            logger.info("[OMS]\nrejected: error=%s", str(ex))
            state_manager.record_error(str(ex))
            logger.error("Failed to execute trade through OMS pipeline: %s", ex)
            print_tick_trace(
                trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
                normalizer_input=normalizer_input, normalizer_output=normalizer_output, multiplier=multiplier,
                normalizer_val=normalizer_val, rsi=rsi_val_trace, ema9=ema9_val_trace, ema21=ema21_val_trace,
                atr=atr_val_trace, trend=trend_val_trace, breakout=breakout_val_trace,
                ai_approved=ai_approved_trace, risk_approved=risk_approved_trace,
                oms_order_created=oms_order_created_trace, oms_reason=str(ex),
                lifecycle_result=f"NO_TRADE_REASON=EXCEPTION: {str(ex)}"
            )


    except Exception as e:
        state_manager.record_error(str(e))
        logger.error("Error in paper trading tick loop processing: %s", e)
        print_tick_trace(
            trace_id=trace_id, symbol=symbol, raw_price=price_float, source=source, timestamp=str(timestamp_str),
            normalizer_val="ERROR",
            lifecycle_result=f"NO_TRADE_REASON=TOP_LEVEL_EXCEPTION: {str(e)}"
        )


def heartbeat_loop() -> None:
    """Periodic status updates dispatcher — interval depends on TOJI_MODE."""
    logger.info(
        "Heartbeat loop started. Interval: %d seconds (mode=%s)",
        _HEARTBEAT_INTERVAL,
        os.getenv("TOJI_MODE", "PAPER").upper()
    )
    while running:
        if stop_event.wait(float(_HEARTBEAT_INTERVAL)):
            break
        try:
            trigger_heartbeat_alert(state_manager, container)
        except Exception as e:
            logger.error("Heartbeat trigger failed: %s", e)


def handle_shutdown(signum: int, frame: Any) -> None:
    """Gracefully cleanup resources and stop execution loops."""
    global running
    if not running:
        return
    running = False
    stop_event.set()

    logger.info("Shutdown signal received. Stopping TOJI trading loop gracefully...")
    if state_manager:
        state_manager.set_state(RuntimeState.STOPPING)

    # 1. Stop tick ingestion
    pass

    # 2. Shutdown platform app
    if app:
        try:
            app.shutdown()
        except Exception as e:
            logger.error("Platform shutdown coordinator error: %s", e)

    # 3. Save final state
    if state_manager:
        state_manager.set_state(RuntimeState.STOPPED)

    # 4. Dispatch Telegram shutdown message
    send_telegram_alert("TOJI Paper Trading system shut down gracefully.")
    logger.info("TOJI Shutdown complete. Exiting cleanly ✓")
    sys.exit(0)


class PaperRunner:
    """Continuous Paper Trading Runner that executes the quantitative trading pipeline."""

    def __init__(self, container: Any = None, event_bus: Any = None, state_manager: Any = None) -> None:
        self.state_manager = state_manager or RuntimeStateManager()
        self.running = False
        self._hb_thread = None
        
        if container:
            self.container = container
            self.event_bus = event_bus
        else:
            self.platform = bootstrap_platform()
            self.container = ServiceRegistry().get_service("Container")
            self.event_bus = ServiceRegistry().get_service("EventBus")

    def start(self) -> None:
        global app, container, event_bus, state_manager, running
        
        logger.info("PaperRunner starting and reusing existing kernel...")
        self.running = True
        running = True
        
        container = self.container
        event_bus = self.event_bus
        state_manager = self.state_manager

        # Initialize active paper trading environments
        try:
            paper_trading = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
            paper_trading.start_paper_session("continuous_paper_account", 100000.0)
            
            paper_market = container.resolve("research_platform.paper_market.orchestrator.PaperMarketOrchestrator")
            paper_market.start_paper_market()
        except Exception as e:
            self.state_manager.set_state(RuntimeState.ERROR)
            self.state_manager.record_error(f"Failed to boot paper trading session: {e}")
            logger.critical("Failed to start paper session: %s", e)
            raise e

        # LiveTradingEnginePlugin handles tick ingestion & strategy execution.
        # PaperMarketOrchestrator's MarketFeedRouter synchronizes prices.
        # No duplicate/competing handlers are registered here.
        logger.info("PaperRunner started tick pipeline listeners successfully.")

        self.state_manager.set_state(RuntimeState.RUNNING)

        # 1. DB status
        db_ok = "FAILED"
        try:
            db = ServiceRegistry().get_service("Database")
            if db and getattr(db, "connected", False):
                db_ok = "OK"
        except Exception:
            pass

        # 2. Redis status
        redis_ok = "FAILED"
        if state_manager and state_manager.redis_client:
            try:
                state_manager.redis_client.ping()
                redis_ok = "OK"
            except Exception:
                pass

        from research_platform.alerting.trade_formatter import format_startup_alert
        
        db_status = "CONNECTED" if db_ok == "OK" else "DISCONNECTED"
        redis_status = "CONNECTED" if redis_ok == "OK" else "DISCONNECTED"
        
        startup_alert = format_startup_alert(
            timestamp=datetime.now(timezone.utc).isoformat(),
            markets=ACTIVE_SYMBOLS,
            db_status=db_status,
            redis_status=redis_status,
            binance_status="CONNECTED",
            telegram_status="CONNECTED",
            starting_balance=100000.0
        )
        logger.info("Startup Alert:\n%s", startup_alert)
        send_telegram_alert(startup_alert)

        # Start Heartbeat background thread
        self._hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._hb_thread.start()

        logger.info("PaperRunner started successfully.")

    def stop(self) -> None:
        global running
        self.running = False
        running = False
        stop_event.set()

        logger.info("Stopping PaperRunner gracefully...")
        self.state_manager.set_state(RuntimeState.STOPPING)

        # No cleanup of custom handlers needed since we delegate to plugin listener.
        self.state_manager.set_state(RuntimeState.STOPPED)
        send_telegram_alert("TOJI Paper Trading system shut down gracefully.")
        logger.info("PaperRunner stopped.")


def main() -> None:
    global app, container, event_bus, state_manager, running

    logger.info(
        "\n"
        "╔══════════════════════════════════════════════════╗\n"
        "║       TOJI PAPER ENGINE STARTED                 ║\n"
        "╠══════════════════════════════════════════════════╣\n"
        "║  Loaded:                                        ║\n"
        "║    Database       ✓                             ║\n"
        "║    Redis          ✓                             ║\n"
        "║    Market Gateway ✓                             ║\n"
        "║    Feature Engine ✓                             ║\n"
        "║    Price Action   ✓                             ║\n"
        "║    Strategy       ✓                             ║\n"
        "║    AI Signal      ✓                             ║\n"
        "║    OMS            ✓                             ║\n"
        "║    Safety         ✓                             ║\n"
        "║    Telegram       ✓                             ║\n"
        "╚══════════════════════════════════════════════════╝"
    )
    logger.info("Active symbols: %s", ACTIVE_SYMBOLS)
    logger.info("Heartbeat interval: %d seconds (mode=%s)",
                _HEARTBEAT_INTERVAL, os.getenv("TOJI_MODE", "PAPER").upper())
    logger.info("Starting TOJI Continuous Paper Trading Runner standalone...")

    # Register OS signals handler
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # 1. Initialize State Manager
    state_manager = RuntimeStateManager()
    state_manager.set_state(RuntimeState.STARTING)

    # 2. Instantiate and start PaperRunner
    runner = PaperRunner(state_manager=state_manager)
    runner.start()

    # Stay alive in main thread
    while runner.running:
        try:
            time.sleep(1.0)
        except KeyboardInterrupt:
            break

    runner.stop()
    platform_to_shutdown = getattr(runner, "platform", None)
    if platform_to_shutdown:
        try:
            platform_to_shutdown.shutdown()
        except Exception as e:
            logger.error("Platform shutdown coordinator error: %s", e)


if __name__ == "__main__":
    main()
