"""Comprehensive Test Suite — Sprint 11A Self Learning Engine Foundation (40 tests)."""

import ast
import pathlib
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from self_learning.dataset_manager import DatasetManager, DatasetRegistered
from self_learning.feature_pipeline import FeaturePipeline
from self_learning.feature_store import FeatureStore, FeatureUpdated
from self_learning.metadata import DatasetMetadata, ModelMetadata, TrainingMetadata
from self_learning.model_manager import ModelManager
from self_learning.model_registry import (
    ModelActivated,
    ModelDeactivated,
    ModelRegistered,
    ModelRegistry,
)
from self_learning.model_versioning import ModelVersioning
from self_learning.models.learning_models import (
    DatasetRecord,
    DatasetStatus,
    FeaturePipelineOutput,
    FeatureRecord,
    FeatureType,
    ModelRecord,
    ModelStatus,
    SemanticVersion,
    TrainingJobRecord,
    TrainingJobStatus,
)
from self_learning.training_jobs import (
    TrainingCompleted,
    TrainingFailed,
    TrainingJobManager,
    TrainingStarted,
)
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def registry(event_bus):
    return ModelRegistry(event_bus=event_bus)


@pytest.fixture
def manager(registry):
    return ModelManager(registry=registry)


@pytest.fixture
def dataset_mgr(event_bus):
    return DatasetManager(event_bus=event_bus)


@pytest.fixture
def feature_store(event_bus):
    return FeatureStore(event_bus=event_bus)


@pytest.fixture
def job_manager(event_bus):
    return TrainingJobManager(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 1. Model Registry — register and retrieve
# ---------------------------------------------------------------------------
def test_model_registry_register(registry):
    record = registry.register_model("price_predictor", model_type="linear")
    assert record.name == "price_predictor"
    assert record.model_type == "linear"
    assert record.status == ModelStatus.REGISTERED
    assert record.is_advisory_only is True


# 2. Model Registry — unregister
def test_model_registry_unregister(registry):
    r = registry.register_model("tmp_model")
    ok = registry.unregister_model(r.model_id)
    assert ok is True
    assert registry.get_model(r.model_id) is None


# 3. Model Registry — list models
def test_model_registry_list_models(registry):
    registry.register_model("m1")
    registry.register_model("m2")
    all_models = registry.list_models()
    assert len(all_models) == 2


# 4. Model Registry — list models filtered by status
def test_model_registry_list_by_status(registry):
    r = registry.register_model("filter_model")
    registry.update_status(r.model_id, ModelStatus.ACTIVE)
    active = registry.list_models(status=ModelStatus.ACTIVE)
    assert any(m.model_id == r.model_id for m in active)


# 5. Model Manager — load and unload
def test_model_manager_load_unload(manager):
    r = manager.registry.register_model("loady")
    loaded = manager.load_model(r.model_id)
    assert loaded.status == ModelStatus.LOADED
    assert manager.is_loaded(r.model_id)

    unloaded = manager.unload_model(r.model_id)
    assert unloaded.status == ModelStatus.INACTIVE
    assert not manager.is_loaded(r.model_id)


# 6. Model Manager — activate model
def test_model_manager_activate(manager):
    r = manager.registry.register_model("activator")
    manager.load_model(r.model_id)
    activated = manager.activate_model(r.model_id)
    assert activated.status == ModelStatus.ACTIVE
    assert manager.is_active(r.model_id)


# 7. Model Manager — deactivate model
def test_model_manager_deactivate(manager):
    r = manager.registry.register_model("deactivator")
    manager.activate_model(r.model_id)
    result = manager.deactivate_model(r.model_id)
    assert result.status == ModelStatus.INACTIVE
    assert not manager.is_active(r.model_id)


# 8. Model Manager — only one active version per name
def test_model_manager_single_active_per_name(manager):
    r1 = manager.registry.register_model("signal_gen", version=SemanticVersion(major=1))
    r2 = manager.registry.register_model("signal_gen", version=SemanticVersion(major=2))

    manager.activate_model(r1.model_id)
    assert manager.is_active(r1.model_id)

    manager.activate_model(r2.model_id)
    assert manager.is_active(r2.model_id)
    assert not manager.is_active(r1.model_id)

    active = manager.get_active_model("signal_gen")
    assert active.model_id == r2.model_id


# 9. Dataset Manager — register dataset
def test_dataset_manager_register(dataset_mgr):
    d = dataset_mgr.register_dataset(
        "ohlcv_2024", feature_columns=["open", "high", "low", "close"], row_count=1000
    )
    assert d.name == "ohlcv_2024"
    assert d.row_count == 1000
    assert d.column_count == 4


# 10. Dataset Manager — dataset versions
def test_dataset_manager_versions(dataset_mgr):
    dataset_mgr.register_dataset("ts_data", feature_columns=["a"], version=SemanticVersion(major=1))
    dataset_mgr.register_dataset("ts_data", feature_columns=["a", "b"], version=SemanticVersion(major=2))
    versions = dataset_mgr.get_versions("ts_data")
    assert len(versions) == 2


# 11. Dataset Manager — metadata attached
def test_dataset_manager_metadata(dataset_mgr):
    d = dataset_mgr.register_dataset("meta_ds", feature_columns=["x"], description="test")
    meta = dataset_mgr.get_metadata(d.dataset_id)
    assert isinstance(meta, DatasetMetadata)
    assert meta.dataset_name == "meta_ds"


# 12. Dataset Manager — dataset validation (valid)
def test_dataset_manager_validation_valid(dataset_mgr):
    d = dataset_mgr.register_dataset("valid_ds", feature_columns=["col1", "col2"])
    ok = dataset_mgr.validate_dataset(d.dataset_id)
    assert ok is True
    refreshed = dataset_mgr.get_dataset(d.dataset_id)
    assert refreshed.status == DatasetStatus.VALID


# 13. Dataset Manager — dataset validation (invalid)
def test_dataset_manager_validation_invalid(dataset_mgr):
    d = dataset_mgr.register_dataset("empty_ds", feature_columns=[])
    ok = dataset_mgr.validate_dataset(d.dataset_id)
    assert ok is False
    refreshed = dataset_mgr.get_dataset(d.dataset_id)
    assert refreshed.status == DatasetStatus.INVALID


# 14. Feature Store — register feature
def test_feature_store_register(feature_store):
    f = feature_store.register_feature("rsi_14", FeatureType.NUMERIC, initial_value=55.3)
    assert f.name == "rsi_14"
    assert f.feature_type == FeatureType.NUMERIC
    assert f.value == 55.3


# 15. Feature Store — update feature
def test_feature_store_update(feature_store):
    feature_store.register_feature("macd", FeatureType.NUMERIC, initial_value=0.0)
    updated = feature_store.update_feature("macd", 1.25)
    assert updated.value == 1.25


# 16. Feature Store — retrieve feature
def test_feature_store_retrieve(feature_store):
    feature_store.register_feature("ema_20", FeatureType.NUMERIC, initial_value=100.0)
    retrieved = feature_store.retrieve_feature("ema_20")
    assert retrieved is not None
    assert retrieved.name == "ema_20"


# 17. Feature Store — feature history preserved
def test_feature_store_history(feature_store):
    feature_store.register_feature("volume_ma", FeatureType.NUMERIC, initial_value=1000.0)
    feature_store.update_feature("volume_ma", 1100.0)
    feature_store.update_feature("volume_ma", 1200.0)
    history = feature_store.get_feature_history("volume_ma")
    assert len(history) == 2
    assert history[0].value == 1000.0
    assert history[1].value == 1100.0


# 18. Feature Store — unknown feature returns None
def test_feature_store_retrieve_missing(feature_store):
    result = feature_store.retrieve_feature("nonexistent_feature")
    assert result is None


# 19. Feature Pipeline — add steps and execute
def test_feature_pipeline_execute():
    pipeline = FeaturePipeline("test_pipeline")

    def multiply_by_two(features: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v * 2 if isinstance(v, (int, float)) else v for k, v in features.items()}

    pipeline.add_step("double", multiply_by_two)
    output = pipeline.execute({"price": 10.0, "volume": 5.0})
    assert output.validation_passed is True
    assert output.features["price"] == 20.0
    assert output.features["volume"] == 10.0
    assert output.output_feature_count == 2


# 20. Feature Pipeline — validation failure captured
def test_feature_pipeline_validation_failure():
    pipeline = FeaturePipeline("strict_pipeline")

    def require_price(features: Dict[str, Any]) -> str | None:
        return None if "price" in features else "Missing required feature 'price'"

    pipeline.add_validator("price_check", require_price)
    output = pipeline.execute({"volume": 100.0})
    assert output.validation_passed is False
    assert len(output.validation_errors) == 1
    assert "price" in output.validation_errors[0]


# 21. Feature Pipeline — immutable output
def test_feature_pipeline_immutable_output():
    pipeline = FeaturePipeline("immut_pipeline")
    output = pipeline.execute({"x": 1})
    with pytest.raises((ValidationError, TypeError)):
        output.validation_passed = False


# 22. Training Jobs — full lifecycle PENDING → RUNNING → COMPLETED
def test_training_job_lifecycle(job_manager, registry):
    r = registry.register_model("nn_model")
    d = DatasetManager().register_dataset("d1", feature_columns=["a"])
    job = job_manager.create_job(r.model_id, d.dataset_id, description="first run")
    assert job.status == TrainingJobStatus.PENDING

    started = job_manager.start_job(job.job_id)
    assert started.status == TrainingJobStatus.RUNNING

    completed = job_manager.complete_job(job.job_id, result_metrics={"accuracy": 0.92})
    assert completed.status == TrainingJobStatus.COMPLETED
    assert completed.result_metrics["accuracy"] == 0.92


# 23. Training Jobs — failure transition
def test_training_job_failure(job_manager, registry):
    r = registry.register_model("failing_model")
    job = job_manager.create_job(r.model_id, "ds_x")
    job_manager.start_job(job.job_id)
    failed = job_manager.fail_job(job.job_id, "OOM error during training")
    assert failed.status == TrainingJobStatus.FAILED
    assert "OOM" in failed.error_message


# 24. Training Jobs — cancel PENDING job
def test_training_job_cancel_pending(job_manager):
    job = job_manager.create_job("model_x", "ds_y")
    cancelled = job_manager.cancel_job(job.job_id)
    assert cancelled.status == TrainingJobStatus.CANCELLED


# 25. Training Jobs — cancel RUNNING job
def test_training_job_cancel_running(job_manager):
    job = job_manager.create_job("model_x", "ds_y")
    job_manager.start_job(job.job_id)
    cancelled = job_manager.cancel_job(job.job_id)
    assert cancelled.status == TrainingJobStatus.CANCELLED


# 26. Training Jobs — metadata recorded on completion
def test_training_job_metadata_recorded(job_manager):
    job = job_manager.create_job("m1", "d1", hyperparameters={"lr": 0.01})
    job_manager.start_job(job.job_id)
    job_manager.complete_job(job.job_id, result_metrics={"loss": 0.05})
    meta = job_manager.get_metadata(job.job_id)
    assert isinstance(meta, TrainingMetadata)
    assert meta.result_metrics["loss"] == 0.05


# 27. Model Versioning — semantic version bumps
def test_model_versioning_bumps():
    v = SemanticVersion(major=1, minor=2, patch=3)
    assert v.bump_patch() == SemanticVersion(major=1, minor=2, patch=4)
    assert v.bump_minor() == SemanticVersion(major=1, minor=3, patch=0)
    assert v.bump_major() == SemanticVersion(major=2, minor=0, patch=0)


# 28. Model Versioning — active version and rollback
def test_model_versioning_rollback():
    versioning = ModelVersioning()
    v1 = SemanticVersion(major=1, minor=0, patch=0)
    v2 = SemanticVersion(major=1, minor=1, patch=0)

    versioning.register_version("m1", v1)
    versioning.register_version("m1", v2)
    versioning.set_active_version("m1", v1)
    versioning.set_active_version("m1", v2)

    assert versioning.get_active_version("m1") == v2
    assert versioning.get_rollback_target("m1") == v1

    rolled_back = versioning.rollback("m1")
    assert rolled_back == v1
    assert versioning.get_active_version("m1") == v1


# 29. Metadata — immutable models
def test_metadata_immutability():
    meta = ModelMetadata(model_id="m1", model_name="test")
    with pytest.raises((ValidationError, TypeError)):
        meta.model_name = "hacked"


# 30. Events — ModelRegistered published
def test_event_model_registered(event_bus, registry):
    events = []
    event_bus.subscribe("ModelRegistered", lambda e: events.append(e))
    registry.register_model("event_model")
    assert len(events) == 1
    assert events[0].event_type == "ModelRegistered"
    assert events[0].model_name == "event_model"


# 31. Events — ModelActivated and ModelDeactivated
def test_event_model_activated_deactivated(event_bus, manager):
    activated_evts = []
    deactivated_evts = []
    event_bus.subscribe("ModelActivated", lambda e: activated_evts.append(e))
    event_bus.subscribe("ModelDeactivated", lambda e: deactivated_evts.append(e))

    r = manager.registry.register_model("evt_model")
    manager.activate_model(r.model_id)
    manager.deactivate_model(r.model_id)

    assert len(activated_evts) == 1
    assert len(deactivated_evts) == 1


# 32. Events — DatasetRegistered published
def test_event_dataset_registered(event_bus, dataset_mgr):
    events = []
    event_bus.subscribe("DatasetRegistered", lambda e: events.append(e))
    dataset_mgr.register_dataset("evt_ds", feature_columns=["x"])
    assert len(events) == 1
    assert events[0].dataset_name == "evt_ds"


# 33. Events — TrainingStarted / TrainingCompleted
def test_event_training_lifecycle(event_bus, job_manager):
    started_evts = []
    completed_evts = []
    event_bus.subscribe("TrainingStarted", lambda e: started_evts.append(e))
    event_bus.subscribe("TrainingCompleted", lambda e: completed_evts.append(e))

    job = job_manager.create_job("m1", "d1")
    job_manager.start_job(job.job_id)
    job_manager.complete_job(job.job_id, {"f1": 0.9})

    assert len(started_evts) == 1
    assert len(completed_evts) == 1
    assert completed_evts[0].result_metrics["f1"] == 0.9


# 34. Events — TrainingFailed
def test_event_training_failed(event_bus, job_manager):
    evts = []
    event_bus.subscribe("TrainingFailed", lambda e: evts.append(e))

    job = job_manager.create_job("m1", "d1")
    job_manager.start_job(job.job_id)
    job_manager.fail_job(job.job_id, "CUDA out of memory")

    assert len(evts) == 1
    assert "CUDA" in evts[0].error_message


# 35. Events — FeatureUpdated
def test_event_feature_updated(event_bus, feature_store):
    evts = []
    event_bus.subscribe("FeatureUpdated", lambda e: evts.append(e))
    feature_store.register_feature("bb_upper", FeatureType.NUMERIC, 50.0)
    feature_store.update_feature("bb_upper", 52.5)
    assert len(evts) == 1
    assert evts[0].feature_name == "bb_upper"


# 36. Thread Safety — concurrent model registration
def test_thread_safety_concurrent_registration(registry):
    errors = []

    def worker(i):
        try:
            for j in range(10):
                registry.register_model(f"model_{i}_{j}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert registry.count() == 50


# 37. Thread Safety — concurrent feature updates
def test_thread_safety_concurrent_feature_updates(feature_store):
    feature_store.register_feature("concurrent_feat", FeatureType.NUMERIC, 0.0)
    errors = []

    def worker(i):
        try:
            for j in range(20):
                feature_store.update_feature("concurrent_feat", float(i * 20 + j))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert feature_store.retrieve_feature("concurrent_feat") is not None


# 38. Performance — feature lookup under 10ms for 1000 features
def test_performance_feature_lookup():
    store = FeatureStore(max_features=1000)
    for i in range(1000):
        store.register_feature(f"feat_{i}", FeatureType.NUMERIC, float(i))

    assert store.count() == 1000

    start_t = time.perf_counter()
    result = store.retrieve_feature("feat_999")
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    assert result is not None
    assert elapsed_ms < 10.0  # SLA: < 10ms


# 39. Regression — paper trading system unaffected
def test_regression_paper_trading_unaffected():
    from paper_trading import PaperOrchestrator
    orch = PaperOrchestrator(initial_capital=100000.0)
    session = orch.start_session()
    assert session.status.value == "RUNNING"
    orch.stop_session()


# 40. Architecture Boundary Enforcement — AST scan
def test_architecture_boundary_enforcement():
    sl_dir = pathlib.Path(__file__).parent.parent / "self_learning"
    forbidden = {"strategy", "broker", "execution", "live_trading", "aws", "monte_carlo"}

    violations = []
    for py_file in sl_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        if f in alias.name:
                            violations.append(f"Forbidden import '{alias.name}' in {py_file.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for f in forbidden:
                        if f in node.module:
                            violations.append(f"Forbidden from-import '{node.module}' in {py_file.name}")

    assert violations == [], f"Architecture violations found: {violations}"


# 41. M-01 — ModelRegistry capacity enforcement
def test_model_registry_capacity_enforcement():
    small_registry = ModelRegistry(max_models=2)
    small_registry.register_model("model_a")
    small_registry.register_model("model_b")

    with pytest.raises(RuntimeError, match="capacity exceeded"):
        small_registry.register_model("model_c")

    # Existing entries are unaffected
    assert small_registry.count() == 2


# 42. M-01 — DatasetManager capacity enforcement
def test_dataset_manager_capacity_enforcement():
    small_mgr = DatasetManager(max_datasets=2)
    small_mgr.register_dataset("ds_a", feature_columns=["x"])
    small_mgr.register_dataset("ds_b", feature_columns=["y"])

    with pytest.raises(RuntimeError, match="capacity exceeded"):
        small_mgr.register_dataset("ds_c", feature_columns=["z"])

    # Existing entries are unaffected
    assert small_mgr.count() == 2
