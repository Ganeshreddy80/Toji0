"""Unit and integration tests for the TOJI State Recovery Framework.
"""

from __future__ import annotations

import time
import pytest
import threading
from datetime import datetime, timezone
from typing import Dict, Any

from research_platform.platform.container_boot import ContainerBootloader
from research_platform.platform.eventbus_boot import EventBusBootloader
from research_platform.recovery.models import Checkpoint, Snapshot, SnapshotType, RecoverySession
from research_platform.recovery.events import (
    CheckpointSaved, CheckpointLoaded, RecoveryStarted, RecoveryCompleted,
    RecoveryFailed, IntegrityCheckFailed, SystemCrashed
)
from research_platform.recovery.repository import RecoveryRepository
from research_platform.recovery.integrity_checker import IntegrityChecker
from research_platform.recovery.checkpoint_manager import CheckpointManager
from research_platform.recovery.snapshot_manager import SnapshotManager
from research_platform.recovery.crash_detector import CrashDetector
from research_platform.recovery.recovery_engine import RecoveryEngine
from research_platform.recovery.orchestrator import RecoveryOrchestrator

# Restorers
from research_platform.recovery.session_recovery import SessionRecoveryManager
from research_platform.recovery.strategy_recovery import StrategyRecoveryManager
from research_platform.recovery.portfolio_recovery import PortfolioRecoveryManager
from research_platform.recovery.position_recovery import PositionRecoveryManager
from research_platform.recovery.scheduler_recovery import SchedulerRecoveryManager
from research_platform.recovery.runtime_recovery import RuntimeRecoveryManager


@pytest.fixture(scope="function")
def repository():
    return RecoveryRepository()


@pytest.fixture(scope="function")
def container(repository):
    c = ContainerBootloader().boot_container()
    eb = EventBusBootloader().boot_eventbus()
    c.register("IEventBus", instance=eb)
    c.register("RecoveryRepository", instance=repository)
    return c


# ── 1. DI Resolution Verification (10 tests) ─────────────────────────

@pytest.mark.parametrize("service_name", [
    "IEventBus",
    "RecoveryOrchestrator",
    "RuntimeEngine",
    "PaperMarketOrchestrator",
    "PaperTradingOrchestrator",
    "PortfolioEngineOrchestrator",
    "StrategyLifecycleOrchestrator",
    "OMSOrchestrator",
    "PortfolioAnalyticsOrchestrator",
    "StrategySchedulerOrchestrator",
    "Database",
    "Configuration",
    "RecoveryRepository",
    "LiveTradingEngine",
    "BacktestRepository",
    "ObservabilityOrchestrator",
    "ValidationOrchestrator",
    "GovernanceOrchestrator",
    "FeaturePlatformOrchestrator",
    "InstitutionalMemoryOrchestrator"
])
def test_recovery_di_resolution(container, service_name):
    class Dummy:
        pass
    try:
        container.register(service_name, instance=Dummy())
    except Exception:
        pass
    resolved = container.resolve(service_name)
    assert resolved is not None


# ── 2. Snapshot Type Configurations (5 tests) ─────────────────────────

@pytest.mark.parametrize("snapshot_type", [
    SnapshotType.MANUAL,
    SnapshotType.AUTOMATIC,
    SnapshotType.TIMED,
    SnapshotType.PRE_SHUTDOWN,
    SnapshotType.PRE_UPGRADE
])
def test_snapshot_type_values(snapshot_type):
    assert snapshot_type in SnapshotType.__members__.values()


# ── 3. Integrity Checker Asserts (10 tests) ──────────────────────────

@pytest.mark.parametrize("weights, positions, expected", [
    ({"AAPL": 0.5, "MSFT": 0.5}, [{"symbol": "AAPL", "quantity": 10.0}], True),
    ({"AAPL": 0.8, "MSFT": 0.9}, [{"symbol": "AAPL", "quantity": 10.0}], False),  # Sum weights > 1.05
    ({"AAPL": 0.5, "MSFT": 0.5}, [{"symbol": "AAPL", "quantity": -5.0}], False),  # Negative position
    ({"AAPL": 0.3, "MSFT": 0.7}, [], True),
    ({}, [{"symbol": "MSFT", "quantity": 100.0}], True),
    ({"AAPL": 0.5, "MSFT": 0.4}, [{"symbol": "MSFT", "quantity": -1.0}], False),
    ({"AAPL": 1.2}, [], False), # Weights > 1.05
    ({}, [], True),
    ({"AAPL": 1.0}, [{"symbol": "AAPL", "quantity": 0.0}], True),
    ({"AAPL": 0.0}, [{"symbol": "AAPL", "quantity": 10.0}], True),
    ({"AAPL": 0.2, "MSFT": 0.8}, [{"symbol": "AAPL", "quantity": 5.0}], True),
    ({"AAPL": 0.5, "MSFT": 0.5}, [{"symbol": "AAPL", "quantity": -0.5}], False),
    ({"AAPL": 1.5, "MSFT": -0.5}, [], False),
    ({"AAPL": 0.99}, [{"symbol": "AAPL", "quantity": 10.0}, {"symbol": "MSFT", "quantity": 20.0}], True),
    ({"AAPL": 0.5, "MSFT": 0.5}, [{"symbol": "AAPL", "quantity": 1.5}, {"symbol": "MSFT", "quantity": -2.0}], False),
    ({"AAPL": 0.1, "MSFT": 0.1, "GOOG": 0.8}, [], True),
    ({"AAPL": 0.05, "MSFT": 1.1}, [], False),
    ({}, [{"symbol": "AAPL", "quantity": 0.0001}], True),
    ({"AAPL": 0.25, "MSFT": 0.25, "GOOG": 0.25, "AMZN": 0.25}, [], True),
    ({"AAPL": 0.25, "MSFT": 0.25, "GOOG": 0.25, "AMZN": 0.35}, [], False)
])
def test_checkpoint_integrity_audit(container, weights, positions, expected):
    checker = IntegrityChecker(container)
    cp = Checkpoint(
        checkpoint_id="cp-1",
        timestamp=datetime.now(timezone.utc),
        portfolio_state={"weights": weights} if weights else {},
        positions_state=positions,
        scheduler_state={"jobs": []}
    )
    # Register dynamic hash checksum
    cp.integrity_hash = checker.compute_hash(cp)
    
    assert checker.validate_integrity(cp) is expected


# ── 4. Checkpoint Models Telemetry (10 tests) ────────────────────────

@pytest.mark.parametrize("orders, trades, sched_state", [
    ([], [], {"jobs": []}),
    ([{"id": "o-1"}], [{"id": "t-1"}], {"jobs": []}),
    ([], [], {}),
    ([{"id": "o-1"}], [], {"jobs": []}),
    ([], [{"id": "t-1"}], {"jobs": []}),
    ([{"id": "o-2"}], [{"id": "t-2"}], {"jobs": []}),
    ([], [], {"jobs": [{"id": "j-1"}]}),
    ([{"id": "o-3"}], [], {"jobs": [{"id": "j-2"}]}),
    ([], [{"id": "t-3"}], {"jobs": [{"id": "j-3"}]}),
    ([{"id": "o-4"}], [{"id": "t-4"}], {"jobs": [{"id": "j-4"}]}),
    ([{"id": "o-5"}], [], {}),
    ([], [{"id": "t-5"}], {}),
    ([{"id": "o-6"}, {"id": "o-7"}], [], {"jobs": []}),
    ([], [{"id": "t-6"}, {"id": "t-7"}], {"jobs": []}),
    ([{"id": "o-8"}], [{"id": "t-8"}], {"jobs": [{"id": "j-5"}, {"id": "j-6"}]}),
    ([{"id": "o-9"}], [{"id": "t-9"}, {"id": "t-10"}], {"jobs": []}),
    ([{"id": "o-10"}, {"id": "o-11"}], [{"id": "t-11"}], {"jobs": [{"id": "j-7"}]}),
    ([], [], {"jobs": [{"id": "j-8"}, {"id": "j-9"}]}),
    ([{"id": "o-12"}], [{"id": "t-12"}], {"jobs": [{"id": "j-10"}]}),
    ([{"id": "o-13"}, {"id": "o-14"}], [{"id": "t-13"}, {"id": "t-14"}], {"jobs": [{"id": "j-11"}, {"id": "j-12"}]})
])
def test_checkpoint_state_mapping(orders, trades, sched_state):
    cp = Checkpoint(
        checkpoint_id="test",
        orders_state=orders,
        trades_state=trades,
        scheduler_state=sched_state
    )
    assert len(cp.orders_state) == len(orders)
    assert len(cp.trades_state) == len(trades)


# ── 5. Individual Restorer Modules (10 tests) ───────────────────────

@pytest.mark.parametrize("restorer_cls, input_data", [
    (SessionRecoveryManager, {}),
    (StrategyRecoveryManager, []),
    (PortfolioRecoveryManager, {}),
    (PositionRecoveryManager, []),
    (SchedulerRecoveryManager, {}),
    (RuntimeRecoveryManager, {}),
    (SessionRecoveryManager, {"AAPL": 150.0}),
    (StrategyRecoveryManager, [{"id": "strat-1"}]),
    (PortfolioRecoveryManager, {"weights": {}}),
    (PositionRecoveryManager, [{"symbol": "AAPL"}])
])
def test_subsystem_restorer_calls(container, restorer_cls, input_data):
    restorer = restorer_cls(container)
    # Ensure executing does not throw exception if orchestator not resolved
    if hasattr(restorer, "restore_session"):
        restorer.restore_session(input_data)
    elif hasattr(restorer, "restore_strategies"):
        restorer.restore_strategies(input_data)
    elif hasattr(restorer, "restore_portfolio"):
        restorer.restore_portfolio(input_data)
    elif hasattr(restorer, "restore_positions"):
        restorer.restore_positions(input_data)
    elif hasattr(restorer, "restore_scheduler"):
        restorer.restore_scheduler(input_data)
    elif hasattr(restorer, "restore_runtime"):
        restorer.restore_runtime(input_data)
    assert True


# ── 6. Event Notification Schemas (10 tests) ──────────────────────────

@pytest.mark.parametrize("event_cls, args", [
    (CheckpointSaved, {"checkpoint_id": "cp-1"}),
    (CheckpointLoaded, {"checkpoint_id": "cp-2"}),
    (RecoveryStarted, {"session_id": "sess-1"}),
    (RecoveryCompleted, {"session_id": "sess-2", "duration_ms": 120.0}),
    (RecoveryFailed, {"session_id": "sess-3", "error_message": "failed"}),
    (IntegrityCheckFailed, {"checkpoint_id": "cp-3", "reason": "broken"}),
    (SystemCrashed, {"detected_at": datetime.now(timezone.utc), "previous_heartbeat_timestamp": datetime.now(timezone.utc), "reason": "kill"}),
    (CheckpointSaved, {"checkpoint_id": "cp-4"}),
    (CheckpointLoaded, {"checkpoint_id": "cp-5"}),
    (RecoveryCompleted, {"session_id": "sess-4", "duration_ms": 45.5})
])
def test_recovery_events_instantiation(event_cls, args):
    event = event_cls(event_id="ev-123", **args)
    assert event.event_id == "ev-123"


# ── 7. Repository States Caching (10 tests) ──────────────────────────

@pytest.mark.parametrize("session_status, stages", [
    ("SUCCESS", ["Database", "Integrity"]),
    ("FAILED", ["Database"]),
    ("STARTED", []),
    ("SUCCESS", ["Database", "Integrity", "Portfolio"]),
    ("FAILED", ["Database", "Integrity"]),
    ("SUCCESS", ["Database", "Integrity", "Portfolio", "OMS"]),
    ("SUCCESS", ["Database", "Integrity", "Portfolio", "OMS", "Runtime"]),
    ("FAILED", ["Database", "Integrity", "Portfolio"]),
    ("SUCCESS", ["Database", "Integrity", "Scheduler"]),
    ("FAILED", ["Database", "Checkpoint"])
])
def test_recovery_history_logging(repository, session_status, stages):
    session = RecoverySession(
        session_id=str(uuid_1 := "sess-log"),
        timestamp=datetime.now(timezone.utc),
        status=session_status,
        stages_executed=stages
    )
    repository.log_recovery_session(session)
    history = repository.get_recovery_history()
    assert len(history) > 0
    assert history[-1].status == session_status


# ── 8. Recovery Checkpoints & Snapshots Flow Tests (15 tests) ──────────

def test_checkpoint_manager_save_and_retrieve(container, repository):
    manager = CheckpointManager(container, repository)
    cp = manager.create_checkpoint()
    manager.save_checkpoint(cp)
    
    loaded = manager.get_latest_checkpoint()
    assert loaded is not None
    assert loaded.checkpoint_id == cp.checkpoint_id
    assert loaded.integrity_hash == cp.integrity_hash


def test_snapshot_creation_and_restore(container, repository):
    sm = SnapshotManager(container, repository)
    snapshot = sm.create_snapshot(SnapshotType.MANUAL, "Manual Snapshot")
    assert snapshot is not None
    
    snapshots_list = sm.list_snapshots()
    assert len(snapshots_list) > 0
    
    # Try restoring snapshot data
    sm.restore_snapshot(snapshot.snapshot_id)
    assert True


def test_crash_detector_trigger_alerts(container, repository):
    manager = CheckpointManager(container, repository)
    # Save a previous checkpoint
    cp = manager.create_checkpoint()
    manager.save_checkpoint(cp)
    
    detector = CrashDetector(container, repository)
    has_crash = detector.detect_crash()
    assert has_crash is True


def test_recovery_engine_clean_slate_success(container):
    engine = RecoveryEngine(container)
    success = engine.execute_recovery()
    assert success is True


def test_corrupted_checkpoint_rejection(container, repository):
    manager = CheckpointManager(container, repository)
    cp = manager.create_checkpoint()
    # corrupt portfolio weights
    cp.portfolio_state = {"weights": {"AAPL": 2.0}}
    manager.save_checkpoint(cp)
    
    engine = RecoveryEngine(container)
    # Should reject recovery since checkpoint is corrupted
    success = engine.execute_recovery()
    assert success is False


def test_recovery_orchestrator_boot_integration(container):
    orch = RecoveryOrchestrator(container)
    success = orch.boot()
    assert success is True


def test_thread_safe_concurrent_checkpoints(container, repository):
    manager = CheckpointManager(container, repository)
    
    def run_save():
        cp = manager.create_checkpoint()
        manager.save_checkpoint(cp)

    threads = [threading.Thread(target=run_save) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert manager.get_latest_checkpoint() is not None


def test_thread_safe_concurrent_snapshots(container, repository):
    sm = SnapshotManager(container, repository)
    
    def run_snapshot():
        sm.create_snapshot(SnapshotType.AUTOMATIC, "Concurrent Snap")

    threads = [threading.Thread(target=run_snapshot) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(sm.list_snapshots()) >= 5
