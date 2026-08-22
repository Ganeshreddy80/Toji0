"""Thread-safe Mock Container Runtime Abstraction for Advisory Operation (Sprint 12B)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ContainerState(str, Enum):
    """Lifecycle states of a container."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    RESTARTING = "RESTARTING"


class ContainerInfo(BaseModel):
    """Immutable descriptor of a managed container instance."""

    container_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Container name.")
    image: str = Field(..., description="Container image tag.")
    state: ContainerState = Field(default=ContainerState.CREATED)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class MockContainerRuntime:
    """Thread-safe Mock Container Runtime abstraction avoiding external daemon dependencies."""

    def __init__(self, max_containers: int = 1000) -> None:
        self._lock = threading.RLock()
        self._max_containers = max_containers
        # container_id -> ContainerInfo
        self._containers: Dict[str, ContainerInfo] = {}

    def create_container(
        self,
        name: str,
        image: str = "toji/service:latest",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ContainerInfo:
        """Create a container descriptor in CREATED state."""
        with self._lock:
            if len(self._containers) >= self._max_containers:
                oldest_id = next(iter(self._containers))
                del self._containers[oldest_id]

            container = ContainerInfo(
                name=name,
                image=image,
                state=ContainerState.CREATED,
                env_vars=env_vars or {},
            )
            self._containers[container.container_id] = container
            logger.info("Created mock container '%s' (id=%s)", name, container.container_id)
            return container

    def start_container(self, container_id: str) -> ContainerInfo:
        """Transition container to RUNNING state."""
        with self._lock:
            c = self._get_or_raise(container_id)
            updated = ContainerInfo(
                container_id=c.container_id,
                name=c.name,
                image=c.image,
                state=ContainerState.RUNNING,
                env_vars=c.env_vars,
                created_at=c.created_at,
            )
            self._containers[container_id] = updated
            logger.info("Started container '%s'", container_id)
            return updated

    def stop_container(self, container_id: str) -> ContainerInfo:
        """Transition container to STOPPED state."""
        with self._lock:
            c = self._get_or_raise(container_id)
            updated = ContainerInfo(
                container_id=c.container_id,
                name=c.name,
                image=c.image,
                state=ContainerState.STOPPED,
                env_vars=c.env_vars,
                created_at=c.created_at,
            )
            self._containers[container_id] = updated
            logger.info("Stopped container '%s'", container_id)
            return updated

    def restart_container(self, container_id: str) -> ContainerInfo:
        """Restart container, transitioning through RESTARTING to RUNNING."""
        with self._lock:
            c = self._get_or_raise(container_id)
            restarted = ContainerInfo(
                container_id=c.container_id,
                name=c.name,
                image=c.image,
                state=ContainerState.RUNNING,
                env_vars=c.env_vars,
                created_at=c.created_at,
            )
            self._containers[container_id] = restarted
            logger.info("Restarted container '%s'", container_id)
            return restarted

    def get_container(self, container_id: str) -> Optional[ContainerInfo]:
        """Lookup container by ID."""
        with self._lock:
            return self._containers.get(container_id)

    def list_containers(self) -> List[ContainerInfo]:
        """List all managed containers."""
        with self._lock:
            return list(self._containers.values())

    def _get_or_raise(self, container_id: str) -> ContainerInfo:
        c = self._containers.get(container_id)
        if not c:
            raise KeyError(f"Container '{container_id}' not found")
        return c

    def clear(self) -> None:
        """Clear all containers."""
        with self._lock:
            self._containers.clear()
