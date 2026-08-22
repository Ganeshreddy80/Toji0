"""Unit tests for the Live Trading Engine.
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.oms.orchestrator import OrderManagementSystemOrchestrator
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from research_platform.live_trading.heartbeat import HeartbeatMonitor
from research_platform.live_trading.models import ActiveSignal, OpenPosition, RecoveryCheckpoint
from research_platform.live_trading.orchestrator import LiveTradingOrchestrator
from research_platform.live_trading.position_manager import PositionManager
from research_platform.live_trading.recovery import RecoveryManager
from research_platform.live_trading.scheduler import ContinuousScheduler
from research_platform.live_trading.session_manager import SessionManager
from research_platform.live_trading.signal_processor import SignalProcessor


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def oms(event_bus):
    return OrderManagementSystemOrchestrator(event_bus)


@pytest.fixture
def ems(event_bus):
    return ExecutionEngineOrchestrator(event_bus)


@pytest.fixture
def orchestrator(event_bus, oms, ems):
    return LiveTradingOrchestrator(event_bus, oms, ems)


def test_continuous_scheduler():
    """Verify scheduler registers tasks and fires background thread loops."""
    scheduler = ContinuousScheduler(interval_seconds=0.01)
    
    fired = 0
    def sample_task():
        nonlocal fired
        fired += 1

    scheduler.register_task(sample_task)
    scheduler.start_scheduler()
    time.sleep(0.05)
    scheduler.stop_scheduler()

    assert fired > 0


def test_signal_processor_filters():
    """Verify duplicate checking and strategy strength constraints."""
    processor = SignalProcessor(min_strength=0.5)

    sig1 = ActiveSignal(signal_id="sig_1", symbol="BTC/USDT", direction="BUY", strength=0.8)
    assert processor.process_signal(sig1) is True

    # Duplicate signal ID check -> rejects
    assert processor.process_signal(sig1) is False

    # Low strength check -> rejects
    sig_weak = ActiveSignal(signal_id="sig_weak", symbol="BTC/USDT", direction="BUY", strength=0.3)
    assert processor.process_signal(sig_weak) is False


def test_position_average_costs():
    """Verify position entry average costs and realized PnL calculations."""
    manager = PositionManager()

    # 1. Buy 1.0 BTC @ 50000 -> Open position
    p1 = manager.update_position("BTC/USDT", quantity=1.0, price=50000.0)
    assert p1.quantity == 1.0
    assert p1.entry_price == 50000.0

    # 2. Buy 1.0 BTC @ 52000 -> Avg entry becomes 51000
    p2 = manager.update_position("BTC/USDT", quantity=1.0, price=52000.0)
    assert p2.quantity == 2.0
    assert p2.entry_price == 51000.0

    # 3. Sell (close) 2.0 BTC @ 53000 -> PnL realized becomes +4000
    p_close = manager.update_position("BTC/USDT", quantity=0.0, price=53000.0)
    assert p_close.quantity == 0.0
    assert manager.realized_pnl == 4000.0


def test_session_lifecycle():
    """Verify session starts and tracks calendar holidays."""
    manager = SessionManager(session_id="session_001")
    assert manager.is_active is False

    # Start
    sess = manager.start_session()
    assert manager.is_active is True
    assert sess.status == "ACTIVE"

    # Holidays checks
    manager.register_holiday("2026-12-25")
    dt = datetime(2026, 12, 25)
    assert manager.is_market_holiday(dt) is True


def test_heartbeat_timeouts():
    """Verify timeout alerts trigger on response thresholds."""
    monitor = HeartbeatMonitor(timeout_limit_ms=200.0)

    # Within bounds -> ALIVE
    h1 = monitor.record_pulse(latency_ms=100.0)
    assert h1.status == "ALIVE"

    # Exceeds bounds -> TIMEOUT
    h2 = monitor.record_pulse(latency_ms=300.0)
    assert h2.status == "TIMEOUT"


def test_checkpoint_state_recovery():
    """Verify checkpoint save and rehydration upon system restart."""
    recovery = RecoveryManager()
    
    pos = OpenPosition(symbol="BTC/USDT", quantity=1.0, entry_price=50000.0, current_price=50000.0, unrealized_pnl=0.0)
    chk = RecoveryCheckpoint(
        checkpoint_id="chk_1",
        session_id="sess_1",
        open_positions=[pos],
        pending_orders=[]
    )

    recovery.save_checkpoint(chk)
    recovered = recovery.recover_state("sess_1")
    
    assert recovered is not None
    assert len(recovered.open_positions) == 1
    assert recovered.open_positions[0].symbol == "BTC/USDT"


def test_live_trading_orchestration(orchestrator, monkeypatch):
    """Verify orchestrator runs startups, processes signals, and checks checkpoints."""
    monkeypatch.setenv("TRADING_MODE", "live")
    orchestrator.start_session("sess_999")

    # Ingest active signal
    sig = ActiveSignal(signal_id="sig_live_1", symbol="BTC/USDT", direction="BUY", strength=0.9)
    success = orchestrator.ingest_market_signal(sig)
    
    assert success is True
    assert len(orchestrator.repository.list_snapshots("sess_999")) == 1

    orchestrator.stop_session("sess_999")
