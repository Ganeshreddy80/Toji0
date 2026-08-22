"""Unit tests for the Institutional Mathematical Research Infrastructure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.feature_platform.events import FeaturePromoted
from research_platform.feature_platform.models import FeatureRecord, FeatureVersionInfo, LineageNode
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return FeaturePlatformOrchestrator(event_bus)


def test_reproducible_versioning(orchestrator):
    """Verify semantic versioning audits can be saved and retrieved."""
    version_info = FeatureVersionInfo(
        uuid=str(uuid.uuid4()),
        feature_name="rsi",
        semantic_version="1.2.0",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        git_commit="git_commit_abc123",
        author="QuantAnalyst",
        experiment_id="exp_009",
        validation_version="val_1.0.0",
        dataset_version="ds_2026_06",
        formula_version="rsi_v1_formula"
    )

    orchestrator.register_version(version_info)
    loaded = orchestrator.version_manager.get_version("rsi", "1.2.0")
    assert loaded is not None
    assert loaded.author == "QuantAnalyst"
    assert loaded.git_commit == "git_commit_abc123"

    versions = orchestrator.version_manager.list_versions("rsi")
    assert len(versions) == 1


def test_provenance_and_impact_traversal(orchestrator):
    """Verify recursive graph tracing backward (lineage) and forward (impact)."""
    # Setup graph dependencies: A -> B -> C
    node_a = LineageNode(node_id="A", name="RawClose", type="raw_column")
    node_b = LineageNode(node_id="B", name="Returns", type="feature", parents=["A"])
    node_c = LineageNode(node_id="C", name="Volatility", type="feature", parents=["B"])

    orchestrator.provenance_graph.register_node(node_a)
    orchestrator.provenance_graph.register_node(node_b)
    orchestrator.provenance_graph.register_node(node_c)

    # Backward Trace (Lineage) of C: should find B and A
    parents = orchestrator.provenance_graph.trace_backward("C")
    assert set(parents) == {"B", "A"}

    # Forward Trace (Impact) of A: should find B and C
    children = orchestrator.provenance_graph.trace_forward("A")
    assert set(children) == {"B", "C"}


def test_lifecycle_promotion_transitions(orchestrator):
    """Verify state transitions and lifecycle validation paths."""
    orchestrator.lifecycle_manager.set_state("rsi", "DRAFT")

    # Valid transitions
    orchestrator.lifecycle_manager.transition_state("rsi", "EXPERIMENTAL")
    assert orchestrator.lifecycle_manager.get_state("rsi") == "EXPERIMENTAL"

    orchestrator.lifecycle_manager.transition_state("rsi", "VALIDATED")
    assert orchestrator.lifecycle_manager.get_state("rsi") == "VALIDATED"

    # Invalid transitions should raise ValueError
    with pytest.raises(ValueError):
        # Cannot jump from VALIDATED to PRODUCTION directly without APPROVED
        orchestrator.lifecycle_manager.transition_state("rsi", "PRODUCTION")


def test_exponential_freshness_decay(orchestrator):
    """Verify decay calculation and freshness score metrics."""
    now = datetime.now(timezone.utc)
    
    # 1. Fresh feature (updated 10 seconds ago)
    metrics_fresh = orchestrator.evaluate_freshness("rsi", now - timedelta(seconds=10))
    assert metrics_fresh.freshness_score > 0.95

    # 2. Stale feature (updated 2 hours ago with half-life of 1 hour)
    metrics_stale = orchestrator.evaluate_freshness("rsi", now - timedelta(hours=2))
    # exp(-ln(2) * 2) = 0.25
    assert 0.24 < metrics_stale.freshness_score < 0.26


def test_importance_coefficient_and_mutual_information(orchestrator):
    """Verify Mutual Info binning and Information Coefficient calculation."""
    np.random.seed(42)
    # Define linear correlation relationship
    X = pd.Series(np.random.normal(0, 1, 100), name="feature_x")
    Y = pd.Series(2.0 * X + np.random.normal(0, 0.5, 100), name="returns_y")

    metrics = orchestrator.calculate_importance("rsi", X, Y)
    
    assert metrics.information_coefficient > 0.8
    assert metrics.mutual_information > 0.2
    assert metrics.information_ratio > 0.0


def test_orthogonal_collinearity_checks(orchestrator):
    """Verify redundancy and recommended actions for correlated features."""
    df = pd.DataFrame({
        "rsi": [1.0, 2.0, 3.0, 4.0],
        "rsi_duplicate": [1.01, 1.99, 3.02, 3.98],
        "close": [10.0, 11.0, 12.0, 13.0]
    })

    report = orchestrator.check_collinearity("rsi", df, threshold=0.85)

    assert report.recommended_action == "REMOVE_REDUNDANT"
    assert "rsi_duplicate" in report.redundant_features
    assert report.maximum_correlation > 0.95


def test_catalog_searches(orchestrator):
    """Verify registry catalog filters by tags and category index."""
    rec = FeatureRecord(
        uuid=str(uuid.uuid4()),
        name="rsi",
        display_name="RSI",
        description="Momentum indicator",
        formula="rsi",
        category="Momentum",
        subcategory="",
        owner="quants",
        author="CTO",
        version="1.0.0",
        tags=["oscillators", "trend"],
        update_frequency="1m",
        warmup_length=0,
        lookback_window=0,
        required_resolution="1m"
    )
    orchestrator.register_feature(rec)

    # Search matches category
    matches_cat = orchestrator.catalog_search(category="Momentum")
    assert len(matches_cat) == 1
    assert matches_cat[0].name == "rsi"

    # Search matches tags
    matches_tags = orchestrator.catalog_search(tags=["oscillators"])
    assert len(matches_tags) == 1


def test_governance_promotion(orchestrator):
    """Verify promotion governor creates signed reports and transitions state."""
    # Pre-register feature definitions
    orchestrator.register_feature(
        FeatureRecord(
            uuid=str(uuid.uuid4()),
            name="close",
            display_name="Close",
            description="Close price",
            formula="close",
            category="Price",
            subcategory="",
            owner="quants",
            author="CTO",
            version="1.0.0",
            update_frequency="1m",
            warmup_length=0,
            lookback_window=0,
            required_resolution="1m"
        )
    )

    times = pd.date_range("2026-06-25 12:00:00", periods=10, freq="1min")
    df = pd.DataFrame({
        "timestamp": times,
        "close": [100.0 + i for i in range(10)],
        "symbol": "BTC/USDT",
        "effective_time": times,
        "as_of": times
    })

    # Set state as VALIDATED before evaluating promotion
    orchestrator.lifecycle_manager.set_state("close", "VALIDATED")

    report = orchestrator.evaluate_promotion("close", df)

    assert report.validation_status == "APPROVED"
    assert report.pit_validation_passed is True
    assert report.approved_by == "CTO_GOVERNANCE_SYSTEM"
    assert orchestrator.lifecycle_manager.get_state("close") == "APPROVED"
