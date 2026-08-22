"""Research Data Platform Orchestrator coordinating versions, trackers, and lineage DAGs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from toji_platform.core.event_bus import IEventBus

from research_platform.data_platform.catalog import MetadataCatalog
from research_platform.data_platform.events import (
    DatasetRegistered,
    DatasetVersioned,
    ExperimentCompleted,
    ExperimentStarted,
    LineageRegistered,
    QualityChecked
)
from research_platform.data_platform.lineage import LineageEngine
from research_platform.data_platform.models import (
    DataQualityReport,
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    LineageRecord
)
from research_platform.data_platform.quality import DataQualityEngine
from research_platform.data_platform.repository import DataPlatformRepository
from research_platform.data_platform.tracker import ExperimentTracker
from research_platform.data_platform.versioning import DatasetVersioning

logger = logging.getLogger(__name__)


class ResearchDataPlatformOrchestrator:
    """Manages tracking repositories, registers schemas, and logs artifacts metadata."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = DataPlatformRepository()
        self._catalog = MetadataCatalog()
        self._tracker = ExperimentTracker()
        self._lineage = LineageEngine()
        self._quality = DataQualityEngine()

    @property
    def repository(self) -> DataPlatformRepository:
        return self._repo

    @property
    def tracker(self) -> ExperimentTracker:
        return self._tracker

    @property
    def lineage(self) -> LineageEngine:
        return self._lineage

    def register_dataset(
        self,
        name: str,
        description: str,
        df: pd.DataFrame,
        version_num: str,
        storage_path: str
    ) -> DatasetVersion:
        """Register a new dataset and create its immutable version details."""
        dataset_id = f"ds_{name.lower().replace(' ', '_')}"
        
        # 1. High level catalog registration
        dataset = Dataset(dataset_id=dataset_id, name=name, description=description)
        self._repo.save_dataset(dataset)
        self._catalog.register_dataset(dataset)
        self._event_bus.publish(DatasetRegistered(payload={"dataset_id": dataset_id}))

        # 2. Content fingerprinting
        fingerprint = DatasetVersioning.generate_fingerprint(df)
        version_id = f"{dataset_id}_v{version_num.replace('.', '_')}"
        size_bytes = len(df.to_csv(index=False).encode("utf-8"))

        version = DatasetVersion(
            version_id=version_id,
            dataset_id=dataset_id,
            version_num=version_num,
            storage_path=storage_path,
            fingerprint=fingerprint,
            size_bytes=size_bytes,
            timestamp=datetime.now(timezone.utc)
        )
        self._repo.save_version(version)

        # 3. Quality assurance audit gate
        report = self._quality.evaluate_quality(version_id, df)
        self._repo.save_quality_report(report)
        self._event_bus.publish(QualityChecked(payload={"report_id": report.report_id, "score": report.score}))

        self._event_bus.publish(DatasetVersioned(payload={"version_id": version_id}))
        logger.info("Successfully registered dataset '%s' version %s with quality score %.2f", name, version_num, report.score)

        return version

    def start_experiment_run(
        self,
        experiment_name: str,
        parameters: Dict[str, Any]
    ) -> ExperimentRun:
        """Register an experiment parameters sweep and initialize trackers."""
        exp_id = f"exp_{experiment_name.lower().replace(' ', '_')}"
        exp = Experiment(experiment_id=exp_id, name=experiment_name, description="Experiment sweep")
        self._catalog.register_experiment(exp)
        self._repo.save_experiment(exp)

        run_id = f"{exp_id}_run_{str(uuid.uuid4())[:8]}"
        run = self._tracker.start_run(run_id, exp_id, parameters)
        self._repo.save_run(run)
        
        self._event_bus.publish(ExperimentStarted(payload={"run_id": run_id}))
        return run

    def log_lineage(self, target_id: str, target_type: str, source_ids: List[str]) -> LineageRecord:
        """Log dependency lineage record to tracking databases."""
        record = LineageRecord(
            lineage_id=str(uuid.uuid4()),
            target_id=target_id,
            target_type=target_type,
            source_ids=source_ids,
            relation_type="computed_from"
        )
        self._lineage.register_lineage(record)
        self._repo.save_lineage(record)
        
        self._event_bus.publish(LineageRegistered(payload={"target_id": target_id}))
        return record
