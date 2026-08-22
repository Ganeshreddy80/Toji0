"""Unit tests for the Research Data Platform.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.data_platform.catalog import MetadataCatalog
from research_platform.data_platform.lineage import LineageEngine
from research_platform.data_platform.models import (
    Dataset,
    DatasetVersion,
    Experiment,
    LineageRecord
)
from research_platform.data_platform.orchestrator import ResearchDataPlatformOrchestrator
from research_platform.data_platform.quality import DataQualityEngine
from research_platform.data_platform.storage import StorageLayer, LazyDataFrameProxy
from research_platform.data_platform.tracker import ExperimentTracker
from research_platform.data_platform.versioning import DatasetVersioning


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return ResearchDataPlatformOrchestrator(event_bus)


def test_dataset_fingerprint_and_schema_check():
    """Verify SHA256 fingerprints change with content tweaks."""
    df1 = pd.DataFrame({"close": [10.0, 11.0], "volume": [100, 200]})
    df2 = pd.DataFrame({"close": [10.0, 11.1], "volume": [100, 200]})  # tweaked value
    
    hash1 = DatasetVersioning.generate_fingerprint(df1)
    hash2 = DatasetVersioning.generate_fingerprint(df2)
    assert hash1.hash_sha256 != hash2.hash_sha256

    # Schema check
    expected = {"close": "float", "volume": "int"}
    assert DatasetVersioning.validate_schema(df1, expected) is True

    # Missing column
    assert DatasetVersioning.validate_schema(df1, {"missing": "float"}) is False


def test_storage_adapters(tmp_path):
    """Verify writing, loading, and lazy loading proxies."""
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    csv_file = os.path.join(tmp_path, "test.csv")
    
    # Save CSV
    size = StorageLayer.save_dataframe(df, csv_file, format_type="CSV")
    assert size > 0

    # Load CSV
    loaded = StorageLayer.load_dataframe(csv_file, format_type="CSV")
    assert len(loaded) == 3

    # Lazy Loading Proxy
    proxy = LazyDataFrameProxy(csv_file, format_type="CSV")
    assert proxy._df is None
    proxy_df = proxy.load()
    assert len(proxy_df) == 3
    assert proxy._df is not None


def test_metadata_catalog():
    """Verify dataset catalogs and tagging queries."""
    catalog = MetadataCatalog()
    
    ds = Dataset(dataset_id="ds_btc", name="BTC/USDT", description="Bitcoin")
    catalog.register_dataset(ds)
    assert catalog.get_dataset("ds_btc") == ds

    exp = Experiment(experiment_id="exp_1", name="Momentum Search", description="Desc", tags=["momentum", "trend"])
    catalog.register_experiment(exp)
    assert catalog.get_experiment("exp_1") == exp
    
    # Tag search
    runs = catalog.search_experiments_by_tag("trend")
    assert "exp_1" in runs


def test_experiment_tracker(tmp_path):
    """Verify parameters logging and artifact registering."""
    tracker = ExperimentTracker()
    run = tracker.start_run(run_id="run_1", experiment_id="exp_1", parameters={"lr": 0.01})
    assert run.status == "RUNNING"

    tracker.log_metrics("run_1", {"accuracy": 0.95})
    run_updated = tracker.get_run("run_1")
    assert run_updated.metrics["accuracy"] == 0.95

    # Log artifact file
    art_file = os.path.join(tmp_path, "weights.txt")
    with open(art_file, "w") as f:
        f.write("weights")
        
    tracker.log_artifact(run_id="run_1", artifact_id="art_1", name="weights", file_path=art_file, category="weights")
    assert len(tracker.get_artifacts("run_1")) == 1

    tracker.complete_run("run_1", "COMPLETED")
    assert tracker.get_run("run_1").status == "COMPLETED"


def test_lineage_engine():
    """Verify upstream dependency lineage traversal."""
    engine = LineageEngine()
    
    # exp_run depends on dataset_1 and feature_1
    rec1 = LineageRecord(lineage_id="l1", target_id="run_1", target_type="run", source_ids=["feature_1"], relation_type="computed_from")
    rec2 = LineageRecord(lineage_id="l2", target_id="feature_1", target_type="feature", source_ids=["dataset_1"], relation_type="computed_from")
    
    engine.register_lineage(rec1)
    engine.register_lineage(rec2)
    
    upstream = engine.get_upstream("run_1")
    assert "feature_1" in upstream
    assert "dataset_1" in upstream


def test_data_quality_checks():
    """Verify duplicate rates and distribution drift detections."""
    quality = DataQualityEngine()

    # Null value and duplicate DataFrame
    df = pd.DataFrame({
        "close": [10.0, 10.0, None, 12.0],
        "volume": [100, 100, 300, 400]
    })
    
    report = quality.evaluate_quality("v1", df)
    # duplicate row at index 1, missing cell at index 2
    assert report.duplicates_count == 1
    assert report.missing_pct > 0.0
    assert report.score < 1.0

    # Drift check
    s1 = pd.Series([10.0, 11.0, 12.0, 11.0, 10.0])
    s2 = pd.Series([100.0, 110.0, 120.0, 110.0, 100.0])  # heavily drifted
    assert DataQualityEngine.detect_distribution_drift(s1, s2) is True


def test_data_platform_orchestration(orchestrator):
    """Verify orchestrator registers datasets and maps lineages."""
    df = pd.DataFrame({"close": [10.0, 11.0], "volume": [100, 200]})
    
    # Ingestion
    ver = orchestrator.register_dataset(
        name="BTC_Data",
        description="Bitcoin market",
        df=df,
        version_num="1.0",
        storage_path="/tmp/btc.csv"
    )
    assert ver.version_num == "1.0"
    assert orchestrator.repository.get_version(ver.version_id) is not None

    # Track Run
    run = orchestrator.start_experiment_run(experiment_name="HyperSweep", parameters={"epochs": 10})
    assert run.status == "RUNNING"

    # Log Lineage
    lineage = orchestrator.log_lineage(target_id="feature_abc", target_type="feature", source_ids=[ver.version_id])
    assert lineage.target_id == "feature_abc"
