"""Thread-safe Service Registry with Dependency Graph Resolution (Sprint 12B)."""

from __future__ import annotations

import collections
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ServiceRecord(BaseModel):
    """Immutable record of a registered microservice version."""

    service_name: str = Field(..., description="Service identifier name.")
    version: str = Field(default="1.0.0", description="Semantic version string.")
    dependencies: List[str] = Field(default_factory=list, description="Names of dependent services.")
    metadata_dict: Dict[str, str] = Field(default_factory=dict)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class ServiceRegistry:
    """Thread-safe Service Registry maintaining registered services and resolving dependency graphs."""

    def __init__(self, max_services: int = 2000) -> None:
        self._lock = threading.RLock()
        self._max_services = max_services
        # service_name -> latest ServiceRecord
        self._services: Dict[str, ServiceRecord] = {}
        # service_name -> list of all registered ServiceRecord versions
        self._history: Dict[str, List[ServiceRecord]] = collections.defaultdict(list)

    def register_service(
        self,
        service_name: str,
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        metadata_dict: Optional[Dict[str, str]] = None,
    ) -> ServiceRecord:
        """Register a new or updated service version."""
        with self._lock:
            if len(self._services) >= self._max_services and service_name not in self._services:
                oldest_name = next(iter(self._services))
                del self._services[oldest_name]
                del self._history[oldest_name]

            record = ServiceRecord(
                service_name=service_name,
                version=version,
                dependencies=dependencies or [],
                metadata_dict=metadata_dict or {},
            )

            self._services[service_name] = record
            self._history[service_name].append(record)

            logger.info("Registered service '%s' v%s with dependencies: %s", service_name, version, record.dependencies)
            return record

    def get_service(self, service_name: str) -> Optional[ServiceRecord]:
        """Lookup latest version of a service by name."""
        with self._lock:
            return self._services.get(service_name)

    def get_version_history(self, service_name: str) -> List[ServiceRecord]:
        """Get history of all registered versions for a service."""
        with self._lock:
            return list(self._history.get(service_name, []))

    def list_services(self) -> List[ServiceRecord]:
        """List all currently registered services."""
        with self._lock:
            return list(self._services.values())

    def resolve_dependency_order(self, target_service: str) -> List[str]:
        """Resolve dependency rollout order using topological sort (dependencies first)."""
        with self._lock:
            visited: Set[str] = set()
            visiting: Set[str] = set()
            order: List[str] = []

            def dfs(name: str) -> None:
                if name in visiting:
                    raise ValueError(f"Circular dependency detected involving service '{name}'")
                if name not in visited:
                    visiting.add(name)
                    rec = self._services.get(name)
                    if rec:
                        for dep in rec.dependencies:
                            dfs(dep)
                    visiting.remove(name)
                    visited.add(name)
                    order.append(name)

            dfs(target_service)
            return order

    def count(self) -> int:
        """Return total count of registered unique services."""
        with self._lock:
            return len(self._services)

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
            self._history.clear()
