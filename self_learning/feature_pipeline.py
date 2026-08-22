"""Thread-safe Feature Pipeline — transform, validate, and emit immutable outputs (Sprint 11A)."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from self_learning.feature_store import FeatureStore
from self_learning.models.learning_models import FeaturePipelineOutput, FeatureType

logger = logging.getLogger(__name__)

# A transformation step: (name, callable) pair
TransformStep = Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]


class FeaturePipeline:
    """Thread-safe feature transformation pipeline producing immutable outputs.

    Each pipeline is composed of an ordered list of transformation steps.
    Steps receive the current feature dict and return an updated dict.
    Validation rules are applied after all transformations.
    """

    def __init__(
        self,
        name: str,
        feature_store: Optional[FeatureStore] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._name = name
        self._feature_store = feature_store or FeatureStore()
        self._steps: List[TransformStep] = []
        self._validators: List[Tuple[str, Callable[[Dict[str, Any]], Optional[str]]]] = []

    @property
    def name(self) -> str:
        return self._name

    def add_step(self, step_name: str, transform_fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Add a named transformation step to the pipeline."""
        with self._lock:
            self._steps.append((step_name, transform_fn))
            logger.debug("Pipeline '%s': added step '%s'", self._name, step_name)

    def add_validator(
        self,
        validator_name: str,
        validator_fn: Callable[[Dict[str, Any]], Optional[str]],
    ) -> None:
        """Add a named validation rule. Validator returns an error string or None if valid."""
        with self._lock:
            self._validators.append((validator_name, validator_fn))

    def execute(self, input_features: Dict[str, Any]) -> FeaturePipelineOutput:
        """Execute the full pipeline on the provided input feature dict.

        Returns an immutable FeaturePipelineOutput. Never raises — validation
        failures are captured in the output's validation_errors list.
        """
        with self._lock:
            steps_snapshot = list(self._steps)
            validators_snapshot = list(self._validators)

        features: Dict[str, Any] = dict(input_features)
        input_count = len(features)
        errors: List[str] = []

        # Apply transformation steps
        for step_name, transform_fn in steps_snapshot:
            try:
                features = transform_fn(features)
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Step '{step_name}' raised {type(exc).__name__}: {exc}"
                errors.append(error_msg)
                logger.warning("Pipeline '%s' step '%s' error: %s", self._name, step_name, exc)

        # Apply validation rules
        for validator_name, validator_fn in validators_snapshot:
            try:
                error = validator_fn(features)
                if error:
                    errors.append(f"[{validator_name}] {error}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Validator '{validator_name}' raised {type(exc).__name__}: {exc}")

        output = FeaturePipelineOutput(
            pipeline_name=self._name,
            features=features,
            validation_passed=len(errors) == 0,
            validation_errors=errors,
            input_feature_count=input_count,
            output_feature_count=len(features),
        )
        logger.info(
            "Pipeline '%s' executed: %d→%d features, valid=%s, errors=%d",
            self._name, input_count, len(features), output.validation_passed, len(errors),
        )
        return output

    def step_count(self) -> int:
        """Return the number of transformation steps registered."""
        with self._lock:
            return len(self._steps)

    def validator_count(self) -> int:
        """Return the number of validation rules registered."""
        with self._lock:
            return len(self._validators)

    def clear(self) -> None:
        """Remove all steps and validators."""
        with self._lock:
            self._steps.clear()
            self._validators.clear()
