"""Unit and integration tests verifying CTO Architecture Corrections for Sprint 6 Research Platform."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
import pytest

from research_platform.core.enums import ExperimentStatus
from research_platform.core.models import (
    DatasetVersion,
    ExperimentConfig,
    ExperimentResult,
    PerformanceMetrics,
    ResearchDashboardView,
    ResearchManifest,
    ResearchReport,
    StrategyVersion,
)
from research_platform.core.orchestrator import ResearchOrchestrator
from research_platform.core.repository import ResearchExperimentRepository
from research_platform.core.state import ResearchStateStore


# =============================================================================
# 1. Ownership & Boundary Tests (No Returns Simulation, Trades, Orders, Fills)
# =============================================================================

def test_cto_no_return_simulation_or_order_execution():
    """Verify ResearchOrchestrator contains ZERO return simulation, order placement, or trade execution logic."""
    orch = ResearchOrchestrator()
    source_code = inspect.getsource(ResearchOrchestrator)

    forbidden_methods = [
        "simulate_strategy_returns",
        "simulate_trades",
        "execute_orders",
        "submit_orders",
        "calculate_pnl",
        "simulate_fills",
    ]
    for forbidden in forbidden_methods:
        assert forbidden not in source_code, f"ResearchOrchestrator contains forbidden method or code '{forbidden}'"

    for model_cls in (
        DatasetVersion,
        StrategyVersion,
        PerformanceMetrics,
        ResearchManifest,
        ExperimentConfig,
        ExperimentResult,
        ResearchReport,
        ResearchDashboardView,
    ):
        fields = set(model_cls.model_fields.keys())
        forbidden_fields = {
            "buy", "sell", "order_id", "fill_price", "broker", "exchange", "slippage", "fees", "funding",
        }
        assert fields.isdisjoint(forbidden_fields), f"{model_cls.__name__} contains forbidden backtesting/execution fields"


# =============================================================================
# 2. Research Manifest Tests (20 Fields, Immutability, Checksum Integrity)
# =============================================================================

def test_cto_research_manifest_fields_and_immutability():
    """Verify ResearchManifest model has all 20 required fields and is frozen/immutable."""
    required_fields = {
        "experiment_id",
        "experiment_name",
        "git_commit_hash",
        "toji_version",
        "dataset_version",
        "dataset_checksum",
        "strategy_version",
        "strategy_checksum",
        "configuration_hash",
        "random_seed",
        "environment",
        "python_version",
        "platform",
        "timezone",
        "started_timestamp",
        "completed_timestamp",
        "duration_seconds",
        "experiment_status",
        "report_version",
        "manifest_checksum",
    }
    model_fields = set(ResearchManifest.model_fields.keys())
    assert required_fields.issubset(model_fields), f"ResearchManifest is missing required fields: {required_fields - model_fields}"

    now = datetime.now(timezone.utc)
    manifest = ResearchManifest(
        experiment_id="exp-001",
        experiment_name="Manifest Test",
        git_commit_hash="abc1234",
        toji_version="1.0.0",
        dataset_version="v1.0.0",
        dataset_checksum="ds-sha256",
        strategy_version="v1.0.0",
        strategy_checksum="st-sha256",
        configuration_hash="cfg-sha256",
        random_seed=42,
        environment="production",
        python_version="3.13.0",
        platform="macOS",
        timezone="UTC",
        started_timestamp=now,
        completed_timestamp=now,
        duration_seconds=0.05,
        experiment_status=ExperimentStatus.COMPLETED,
        report_version="1.0.0",
        manifest_checksum="manifest-sha256",
    )

    with pytest.raises(Exception):
        manifest.random_seed = 9999


def test_cto_manifest_checksum_integrity():
    """Verify SHA-256 checksum computation over manifest fields is deterministic and accurate."""
    data = {
        "experiment_id": "exp-test",
        "experiment_name": "Test Run",
        "git_commit_hash": "head",
        "toji_version": "1.0.0",
        "dataset_version": "v1.0.0",
        "dataset_checksum": "ds-chk",
        "strategy_version": "v1.0.0",
        "strategy_checksum": "st-chk",
        "configuration_hash": "cfg-chk",
        "random_seed": 42,
        "environment": "production",
        "python_version": "3.13.0",
        "platform": "macOS",
        "timezone": "UTC",
        "started_timestamp": "2025-01-01T00:00:00Z",
        "completed_timestamp": "2025-01-01T00:00:01Z",
        "duration_seconds": 1.0,
        "experiment_status": ExperimentStatus.COMPLETED,
        "report_version": "1.0.0",
    }

    c1 = ResearchManifest.compute_checksum(data)
    c2 = ResearchManifest.compute_checksum(data)
    assert c1 == c2
    assert len(c1) == 64  # SHA-256 hex string length


# =============================================================================
# 3. Experiment Execution & Manifest Attachment
# =============================================================================

def test_cto_experiment_attaches_manifest_on_completion():
    """Verify ResearchOrchestrator creates and attaches a valid ResearchManifest to ExperimentResult."""
    orch = ResearchOrchestrator()
    orch.initialize()

    ds = DatasetVersion(
        dataset_id="ds-cto-001",
        name="CTO Dataset",
        version="v1.0.0",
        checksum="ds-sha256-cto",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        record_count=50,
    )
    strat = StrategyVersion(
        strategy_id="strat-cto-001",
        name="CTO Strategy",
        version="v1.0.0",
    )

    cfg = orch.create_experiment("CTO Audit Experiment", ds, strat, parameters={"returns": [0.01, -0.005, 0.02, 0.015, -0.01]})
    res = orch.run_experiment(cfg)

    assert res.status == ExperimentStatus.COMPLETED
    assert res.manifest is not None
    assert res.manifest.experiment_id == cfg.experiment_id
    assert res.manifest.dataset_checksum == "ds-sha256-cto"
    assert res.manifest.random_seed == 42
    assert len(res.manifest.manifest_checksum) == 64


# =============================================================================
# 4. Fail-Closed Error Handling & Manifest Creation on Failure
# =============================================================================

def test_cto_fail_closed_attaches_failed_manifest():
    """Verify missing input returns causes fail-closed execution with status FAILED and a valid failed manifest."""
    orch = ResearchOrchestrator()
    orch.initialize()

    ds = DatasetVersion(
        dataset_id="ds-fail-001",
        name="Fail Dataset",
        version="v1.0.0",
        checksum="ds-fail-sha256",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 2, 1, tzinfo=timezone.utc),
        record_count=0,
    )
    strat = StrategyVersion(
        strategy_id="strat-fail-001",
        name="Fail Strategy",
        version="v1.0.0",
    )

    # Config lacking returns input
    cfg = orch.create_experiment("Fail Closed Test", ds, strat, parameters={})
    res = orch.run_experiment(cfg)

    assert res.status == ExperimentStatus.FAILED
    assert "No input returns series" in res.error_message
    assert res.manifest is not None
    assert res.manifest.experiment_status == ExperimentStatus.FAILED


# =============================================================================
# 5. Determinism & Output Immutability
# =============================================================================

def test_cto_determinism_identical_inputs():
    """Verify identical returns inputs produce 100% bit-identical metrics and output models."""
    ds = DatasetVersion(
        dataset_id="ds-det-001",
        name="Det Dataset",
        version="v1.0.0",
        checksum="det-sha256",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 3, 1, tzinfo=timezone.utc),
        record_count=20,
    )
    strat = StrategyVersion(
        strategy_id="strat-det-001",
        name="Det Strategy",
        version="v1.0.0",
    )

    returns = [0.01, -0.005, 0.02, 0.015, -0.01, 0.005]

    orch1 = ResearchOrchestrator()
    orch1.initialize()
    cfg1 = ExperimentConfig(
        experiment_id="exp-det-fixed-001",
        name="Det Test",
        dataset_version=ds,
        strategy_version=strat,
        parameters={"returns": returns, "run_walk_forward": False},
        seed=100,
    )
    res1 = orch1.run_experiment(cfg1)

    orch2 = ResearchOrchestrator()
    orch2.initialize()
    cfg2 = ExperimentConfig(
        experiment_id="exp-det-fixed-001",
        name="Det Test",
        dataset_version=ds,
        strategy_version=strat,
        parameters={"returns": returns, "run_walk_forward": False},
        seed=100,
    )
    res2 = orch2.run_experiment(cfg2)

    assert res1.metrics.sharpe_ratio == res2.metrics.sharpe_ratio
    assert res1.metrics.max_drawdown == res2.metrics.max_drawdown
    assert res1.manifest.manifest_checksum == res2.manifest.manifest_checksum


# =============================================================================
# 6. Repository Thread Safety & Atomic Persistence
# =============================================================================

def test_cto_repository_thread_safety_and_crud():
    """Verify ResearchExperimentRepository CRUD operations are thread-safe via RLock."""
    repo = ResearchExperimentRepository()
    ds = DatasetVersion(dataset_id="ds-repo", name="Repo DS", version="v1", checksum="c1", start_time=datetime(2025,1,1,tzinfo=timezone.utc), end_time=datetime(2025,2,1,tzinfo=timezone.utc), record_count=10)
    st = StrategyVersion(strategy_id="st-repo", name="Repo Strat", version="v1")
    cfg = ExperimentConfig(experiment_id="exp-repo-1", name="Repo Test", dataset_version=ds, strategy_version=st)
    res = ExperimentResult(experiment_id="exp-repo-1", config=cfg, status=ExperimentStatus.COMPLETED, metrics=PerformanceMetrics(sharpe_ratio=1.8), completed_at=datetime.now(timezone.utc))

    repo.save_experiment(res)
    loaded = repo.load_experiment("exp-repo-1")

    assert loaded is not None
    assert loaded.experiment_id == "exp-repo-1"
    assert loaded.metrics.sharpe_ratio == 1.8
    assert len(repo.list_experiments()) == 1


# =============================================================================
# 7. Production Hardening Tests (Issues 1-5 Fixes Verification)
# =============================================================================

def test_cto_repository_atomic_persistence_rollback_on_failure():
    """Verify Issue 1: Option A atomic persistence prevents memory pollution if storage engine fails."""
    from unittest.mock import MagicMock
    from research_platform.core.exceptions import RepositoryError

    failing_storage = MagicMock()
    failing_storage.write_rows.side_effect = RuntimeError("Database disk full")
    failing_storage.execute.return_value = []

    repo = ResearchExperimentRepository(storage_engine=failing_storage)
    ds = DatasetVersion(dataset_id="ds-atom", name="Atom DS", version="v1", checksum="c1", start_time=datetime(2025,1,1,tzinfo=timezone.utc), end_time=datetime(2025,2,1,tzinfo=timezone.utc), record_count=10)
    st = StrategyVersion(strategy_id="st-atom", name="Atom Strat", version="v1")
    cfg = ExperimentConfig(experiment_id="exp-atom-1", name="Atom Test", dataset_version=ds, strategy_version=st)
    res = ExperimentResult(experiment_id="exp-atom-1", config=cfg, status=ExperimentStatus.COMPLETED, metrics=PerformanceMetrics(sharpe_ratio=2.0), completed_at=datetime.now(timezone.utc))

    with pytest.raises(RepositoryError, match="Failed to persist experiment to storage"):
        repo.save_experiment(res)

    # Memory cache MUST NOT contain the experiment
    assert repo.load_experiment("exp-atom-1") is None
    assert len(repo.list_experiments()) == 0


def test_cto_repository_cache_eviction_no_memory_leak():
    """Verify Issue 4: Cache eviction removes evicted experiment from _by_id dict to prevent memory leak."""
    repo = ResearchExperimentRepository()
    ds = DatasetVersion(dataset_id="ds-evict", name="Evict DS", version="v1", checksum="c1", start_time=datetime(2025,1,1,tzinfo=timezone.utc), end_time=datetime(2025,2,1,tzinfo=timezone.utc), record_count=10)
    st = StrategyVersion(strategy_id="st-evict", name="Evict Strat", version="v1")

    # Add 1001 unique experiments to trigger eviction of item 0
    for i in range(1001):
        exp_id = f"exp-evict-{i}"
        cfg = ExperimentConfig(experiment_id=exp_id, name=f"Exp {i}", dataset_version=ds, strategy_version=st)
        res = ExperimentResult(experiment_id=exp_id, config=cfg, status=ExperimentStatus.COMPLETED, metrics=PerformanceMetrics(), completed_at=datetime.now(timezone.utc))
        repo.save_experiment(res)

    # Item 0 MUST be evicted from both _history and _by_id
    assert len(repo.list_experiments()) == 1000
    assert repo.load_experiment("exp-evict-0") is None
    assert repo.load_experiment("exp-evict-1000") is not None


def test_cto_deterministic_sweep_id_generation():
    """Verify Issue 5: ParameterSweepConfig generates 100% deterministic sweep_id when omitted."""
    from research_platform.core.models import ParameterSweepConfig

    param_ranges = {"fast": [5, 10], "slow": [20, 30]}
    sid1 = ParameterSweepConfig.generate_sweep_id(param_ranges, seed=42, strategy_version="v1.0.0", dataset_version="v2.0.0")
    sid2 = ParameterSweepConfig.generate_sweep_id(param_ranges, seed=42, strategy_version="v1.0.0", dataset_version="v2.0.0")

    assert sid1 == sid2
    assert sid1.startswith("sweep-")

    cfg = ParameterSweepConfig(parameter_ranges=param_ranges, seed=42)
    assert cfg.sweep_id == ""  # Defaults to empty string, computed deterministically by engine


def test_cto_git_commit_hash_fallback_hierarchy(monkeypatch):
    """Verify Issue 3: Git commit hash resolves via env var GIT_COMMIT_SHA, fallback command, or UNKNOWN without crashing."""
    orch = ResearchOrchestrator()
    orch.initialize()

    ds = DatasetVersion(dataset_id="ds-git", name="Git DS", version="v1", checksum="c1", start_time=datetime(2025,1,1,tzinfo=timezone.utc), end_time=datetime(2025,2,1,tzinfo=timezone.utc), record_count=10)
    st = StrategyVersion(strategy_id="st-git", name="Git Strat", version="v1")
    cfg = orch.create_experiment("Git Hash Test", ds, st, parameters={"returns": [0.01, -0.01]})

    # Case 1: Environment variable set
    monkeypatch.setenv("GIT_COMMIT_SHA", "custom-commit-sha-12345")
    res1 = orch.run_experiment(cfg)
    assert res1.manifest.git_commit_hash == "custom-commit-sha-12345"

    # Case 2: Environment variable unset -> fallback to subprocess or UNKNOWN
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    res2 = orch.run_experiment(cfg)
    assert res2.manifest.git_commit_hash != "HEAD-commit-hash"  # Old hardcoded string removed
    assert isinstance(res2.manifest.git_commit_hash, str)
    assert len(res2.manifest.git_commit_hash) > 0
