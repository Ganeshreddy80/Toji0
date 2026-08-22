"""Self Learning Engine — Sprint 11A package init."""

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

__all__ = [
    # Domain models
    "SemanticVersion",
    "ModelRecord",
    "ModelStatus",
    "DatasetRecord",
    "DatasetStatus",
    "FeatureRecord",
    "FeatureType",
    "TrainingJobRecord",
    "TrainingJobStatus",
    "FeaturePipelineOutput",
    # Metadata
    "ModelMetadata",
    "DatasetMetadata",
    "TrainingMetadata",
    # Components
    "ModelRegistry",
    "ModelManager",
    "ModelVersioning",
    "DatasetManager",
    "FeatureStore",
    "FeaturePipeline",
    "TrainingJobManager",
    # Events
    "ModelRegistered",
    "ModelActivated",
    "ModelDeactivated",
    "DatasetRegistered",
    "FeatureUpdated",
    "TrainingStarted",
    "TrainingCompleted",
    "TrainingFailed",
]
