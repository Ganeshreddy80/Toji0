"""TOJI Heartbeat system evaluating connectivity, memory, and performance metrics.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from research_platform.platform.service_registry import ServiceRegistry
from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel

logger = logging.getLogger(__name__)


def run_heartbeat_check(state_manager: Any, container: Any = None) -> str:
    """Check connections, memory, and runtime metrics, formatting a Telegram status string."""
    if container is None:
        try:
            container = ServiceRegistry().get_service("Container")
        except Exception:
            pass

    # 1. DB status
    db_ok = "FAILED"
    try:
        db = None
        if container and container.has("Database"):
            db = container.resolve("Database")
        else:
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

    # 3. Market Feed status
    market_status = "DISCONNECTED"
    try:
        if container and (
            container.has("BinanceDemoGateway") or 
            container.has("MarketGateway") or 
            container.has("BinanceExchangeProvider")
        ):
            market_status = "CONNECTED"
    except Exception:
        pass

    # 4. OMS status
    oms_status = "FAILED"
    try:
        if container and (
            container.has("OmsCore") or 
            container.has("OrderManagementSystemOrchestrator")
        ):
            oms_status = "OK"
    except Exception:
        pass

    # 5. Safety status (Risk Engine / KillSwitch)
    safety_status = "INACTIVE"
    try:
        if container:
            from research_platform.risk_management.orchestrator import RiskManagementOrchestrator
            risk_orch = container.resolve(RiskManagementOrchestrator)
            if risk_orch:
                safety_status = "INACTIVE" if risk_orch.kill_switch.is_activated else "ACTIVE"
    except Exception:
        pass

    # 6. Memory usage
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)
        mem_str = f"{mem_mb:.1f} MB"
    except Exception:
        mem_str = "UNKNOWN"

    # Compute Uptime
    uptime_str = "00:00:00"
    if state_manager and state_manager.start_time:
        uptime = datetime.now(timezone.utc) - state_manager.start_time
        total_seconds = int(uptime.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    ticks = state_manager.processed_ticks if state_manager else 0
    signals = state_manager.generated_signals if state_manager else 0
    trades = state_manager.executed_paper_trades if state_manager else 0

    # 7. Portfolio balance & PnL
    balance = 100000.0
    pnl = 0.0
    try:
        if container:
            portfolio_store = container.resolve("PortfolioStateStore")
            if portfolio_store:
                snap = portfolio_store.get_current_snapshot()
                if snap:
                    balance = getattr(snap.metrics, "portfolio_value", 100000.0)
                    pnl = getattr(snap.metrics, "total_realized_pnl", 0.0) + getattr(snap.metrics, "total_unrealized_pnl", 0.0)
    except Exception:
        pass

    # Active symbols watchlist
    symbols_env = os.getenv("BINANCE_SYMBOLS", "BTCUSDT,ETHUSDT")
    watching_list = [s.strip() for s in symbols_env.split(",") if s.strip()]

    from research_platform.alerting.trade_formatter import format_heartbeat_alert
    status_msg = format_heartbeat_alert(
        uptime=uptime_str,
        market_status=market_status,
        watching=watching_list,
        ticks=ticks,
        signals=signals,
        trades=trades,
        balance=balance,
        pnl=pnl,
        db_status=db_ok,
        redis_status=redis_ok,
        memory=mem_str,
        safety_status=safety_status
    )
    
    return status_msg


def trigger_heartbeat_alert(state_manager: Any, container: Any = None) -> None:
    """Generate status report and dispatch via Telegram channel."""
    status_msg = run_heartbeat_check(state_manager, container)
    try:
        if container is None:
            container = ServiceRegistry().get_service("Container")
        
        if container:
            alert_orch = container.resolve("AlertOrchestrator")
            if alert_orch:
                alert = Alert(
                    title="TOJI STATUS",
                    message=status_msg,
                    severity=AlertSeverity.HIGH,
                    channels=[AlertChannel.TELEGRAM]
                )
                alert_orch.fire(alert)
                logger.info("Heartbeat alert successfully dispatched.")
    except Exception as e:
        logger.warning("Heartbeat alert dispatch failed: %s", e)
