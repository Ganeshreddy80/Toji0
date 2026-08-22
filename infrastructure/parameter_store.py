"""Thread-safe Systems Manager Parameter Store Abstraction with Versioning and Bounded Cache (Sprint 12A)."""

from __future__ import annotations

import collections
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ParameterDescriptor(BaseModel):
    """Immutable descriptor of an SSM parameter with version tracking."""

    name: str = Field(..., description="Parameter key name.")
    value: Any = Field(..., description="Parameter value.")
    value_type: str = Field(default="String", description="Parameter type (String, StringList, SecureString).")
    version: int = Field(default=1, ge=1, description="Monotonic version number.")
    arn: str = Field(default="", description="Parameter ARN.")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class ParameterStore:
    """Thread-safe Parameter Store supporting registration, lookup, version tracking, and bounded cache (up to 10,000 parameters)."""

    def __init__(self, max_parameters: int = 10000) -> None:
        self._lock = threading.RLock()
        self._max_parameters = max_parameters
        # parameter_name -> ParameterDescriptor (latest)
        self._latest: Dict[str, ParameterDescriptor] = {}
        # parameter_name -> version_history list
        self._history: Dict[str, List[ParameterDescriptor]] = collections.defaultdict(list)

    def register_parameter(
        self,
        name: str,
        value: Any,
        value_type: str = "String",
        arn: Optional[str] = None,
    ) -> ParameterDescriptor:
        """Register or update a parameter value, incrementing version automatically."""
        with self._lock:
            if len(self._latest) >= self._max_parameters and name not in self._latest:
                oldest_name = next(iter(self._latest))
                del self._latest[oldest_name]
                del self._history[oldest_name]

            param_arn = arn or f"arn:aws:ssm:us-east-1:123456789012:parameter/{name.lstrip('/')}"
            prev = self._latest.get(name)
            new_version = (prev.version + 1) if prev else 1

            descriptor = ParameterDescriptor(
                name=name,
                value=value,
                value_type=value_type,
                version=new_version,
                arn=param_arn,
            )

            self._latest[name] = descriptor
            self._history[name].append(descriptor)

            logger.info("Registered parameter '%s' v%d (type='%s')", name, new_version, value_type)
            return descriptor

    def get_parameter(self, name: str) -> Optional[ParameterDescriptor]:
        """Lookup latest version of parameter by name."""
        with self._lock:
            return self._latest.get(name)

    def get_parameter_version(self, name: str, version: int) -> Optional[ParameterDescriptor]:
        """Lookup specific version of parameter."""
        with self._lock:
            history = self._history.get(name, [])
            for desc in history:
                if desc.version == version:
                    return desc
            return None

    def list_parameters(self) -> List[ParameterDescriptor]:
        """List all current parameter descriptors."""
        with self._lock:
            return list(self._latest.values())

    def count(self) -> int:
        """Return count of registered parameter keys."""
        with self._lock:
            return len(self._latest)

    def clear(self) -> None:
        """Clear all parameter entries."""
        with self._lock:
            self._latest.clear()
            self._history.clear()
