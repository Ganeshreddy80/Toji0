"""Thread-safe Dependency Graph & Impact Analyzer for Mission Control (Sprint 10C)."""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class DependencyNode(BaseModel):
    """Immutable representation of a service node in the dependency graph."""

    service_name: str = Field(..., description="Service identifier.")
    dependencies: List[str] = Field(default_factory=list, description="Services this service depends on.")
    dependents: List[str] = Field(default_factory=list, description="Services depending on this service.")

    model_config = ConfigDict(frozen=True)


class DependencyManager:
    """Thread-safe Dependency Graph Manager tracking service topology, cycle detection, and impact propagation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._graph: Dict[str, Set[str]] = collections.defaultdict(set)  # service -> dependencies (upstream)
        self._reverse_graph: Dict[str, Set[str]] = collections.defaultdict(set)  # service -> dependents (downstream)
        self._failed_services: Set[str] = set()

    def add_dependency(self, service_name: str, depends_on: str) -> bool:
        """Add a dependency relationship: service_name depends on depends_on.

        Returns True if added successfully, False if self-dependency or cycle detected.
        """
        with self._lock:
            if service_name == depends_on:
                logger.warning("Rejected self-dependency for '%s'", service_name)
                return False

            # Check if adding (service_name -> depends_on) introduces a cycle.
            # A cycle occurs if service_name is reachable from depends_on in reverse graph (or graph downstream).
            if self._is_reachable(from_service=service_name, target_service=depends_on):
                logger.warning("Rejected cyclic dependency: %s -> %s", service_name, depends_on)
                return False

            self._graph[service_name].add(depends_on)
            self._reverse_graph[depends_on].add(service_name)
            # Ensure nodes exist in both graphs
            _ = self._graph[depends_on]
            _ = self._reverse_graph[service_name]
            logger.info("Added dependency: '%s' depends on '%s'", service_name, depends_on)
            return True

    def remove_dependency(self, service_name: str, depends_on: str) -> bool:
        """Remove a dependency relationship."""
        with self._lock:
            if service_name in self._graph and depends_on in self._graph[service_name]:
                self._graph[service_name].remove(depends_on)
                self._reverse_graph[depends_on].remove(service_name)
                return True
            return False

    def get_dependencies(self, service_name: str) -> List[str]:
        """Get direct upstream dependencies for a service."""
        with self._lock:
            return sorted(list(self._graph.get(service_name, set())))

    def get_dependents(self, service_name: str) -> List[str]:
        """Get direct downstream dependents relying on a service."""
        with self._lock:
            return sorted(list(self._reverse_graph.get(service_name, set())))

    def record_service_failure(self, service_name: str) -> List[str]:
        """Record service failure and return list of all impacted downstream dependent services."""
        start_t = time.perf_counter()
        with self._lock:
            self._failed_services.add(service_name)
            impacted = self.get_affected_dependents(service_name)
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            logger.debug("Dependency failure traversal for '%s' completed in %.3f ms (%d impacted)", service_name, elapsed_ms, len(impacted))
            return impacted

    def record_service_recovery(self, service_name: str) -> None:
        """Record service recovery."""
        with self._lock:
            self._failed_services.discard(service_name)

    def get_affected_dependents(self, failed_service: str) -> List[str]:
        """Get all downstream services transitively affected by failed_service."""
        with self._lock:
            visited: Set[str] = set()
            queue = collections.deque(self._reverse_graph.get(failed_service, set()))

            while queue:
                current = queue.popleft()
                if current not in visited:
                    visited.add(current)
                    queue.extend(self._reverse_graph.get(current, set()))

            return sorted(list(visited))

    def has_failed_dependencies(self, service_name: str) -> Tuple[bool, List[str]]:
        """Check if any upstream dependency for service_name is currently failed.

        Returns (has_failed_dep: bool, failed_dep_names: List[str]).
        """
        with self._lock:
            direct_deps = self._graph.get(service_name, set())
            failed_deps = [dep for dep in direct_deps if dep in self._failed_services]
            return len(failed_deps) > 0, sorted(failed_deps)

    def _is_reachable(self, from_service: str, target_service: str) -> bool:
        """Check if target_service is reachable from from_service via downstream dependent links."""
        visited: Set[str] = set()
        queue = collections.deque([from_service])

        while queue:
            curr = queue.popleft()
            if curr == target_service:
                return True
            if curr not in visited:
                visited.add(curr)
                queue.extend(self._reverse_graph.get(curr, set()))

        return False

    def get_all_nodes(self) -> Dict[str, DependencyNode]:
        """Get full graph view as dict of DependencyNodes."""
        with self._lock:
            all_services = set(self._graph.keys()).union(set(self._reverse_graph.keys()))
            result = {}
            for svc in all_services:
                result[svc] = DependencyNode(
                    service_name=svc,
                    dependencies=sorted(list(self._graph.get(svc, set()))),
                    dependents=sorted(list(self._reverse_graph.get(svc, set()))),
                )
            return result

    def clear(self) -> None:
        """Clear dependency graph and failure records."""
        with self._lock:
            self._graph.clear()
            self._reverse_graph.clear()
            self._failed_services.clear()
