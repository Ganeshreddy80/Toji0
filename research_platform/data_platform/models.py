"""Immutable Pydantic models for the Research Data Platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DatasetFingerprint(BaseModel):
    """SHA256 checksum and identity container."""

    hash_sha256: str

    model_config = ConfigDict(frozen=True)


class DatasetStatistics(BaseModel):
    """Computed statistics summary."""

    mean_values: Dict[str, float] = Field(default_factory=dict)
    std_values: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class Dataset(BaseModel):
    """High-level catalog dataset registration."""

    dataset_id: str
    name: str
    description: str
    created_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class DatasetVersion(BaseModel):
    """Specific revision index mapping immutable records."""

    version_id: str
    dataset_id: str
    version_num: str
    storage_path: str
    fingerprint: DatasetFingerprint
    size_bytes: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class DatasetManifest(BaseModel):
    """Structural details mapping columns and row counts."""

    version_id: str
    columns: List[str] = Field(default_factory=list)
    column_types: Dict[str, str] = Field(default_factory=dict)
    row_count: int

    model_config = ConfigDict(frozen=True)


class DatasetPartition(BaseModel):
    """Sub-partition keys targeting storage filters."""

    partition_id: str
    version_id: str
    filter_values: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class FeatureSnapshot(BaseModel):
    """PIT aligned cached points summaries."""

    snapshot_id: str
    feature_name: str
    version: str
    values_fingerprint: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class Experiment(BaseModel):
    """Categorized sweeps grouping related parameter runs."""

    experiment_id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    created_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExperimentRun(BaseModel):
    """A single execution sweep trial tracking parameters and artifacts."""

    run_id: str
    experiment_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExperimentArtifact(BaseModel):
    """Saved output documents (e.g. models, weights, tables, configurations)."""

    artifact_id: str
    run_id: str
    name: str
    file_path: str
    category: str
    size_bytes: int

    model_config = ConfigDict(frozen=True)


class MetadataRecord(BaseModel):
    """KeyValue tags indexing runs or sets."""

    record_id: str
    entity_id: str
    key: str
    value: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class DataQualityReport(BaseModel):
    """Quality assurance checks outcomes."""

    report_id: str
    dataset_version_id: str
    score: float
    missing_pct: float
    duplicates_count: int
    drift_status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class LineageRecord(BaseModel):
    """Source dependency connections DAG map."""

    lineage_id: str
    target_id: str
    target_type: str  # dataset, feature, strategy, backtest
    source_ids: List[str] = Field(default_factory=list)
    relation_type: str  # computed_from, backtested_on
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExperimentTag(BaseModel):
    """Experiment tags."""

    name: str

    model_config = ConfigDict(frozen=True)
