"""Thread-safe Resource Allocator for simulated execution environment (Sprint 11B)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ResourceReservation(BaseModel):
    """Immutable record of a resource reservation."""

    reservation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = Field(..., description="Associated pipeline identifier.")
    cpu_cores: float = Field(..., gt=0.0, description="Allocated CPU cores.")
    memory_mb: float = Field(..., gt=0.0, description="Allocated memory in MB.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ResourceAllocator:
    """Thread-safe allocator managing simulated compute resource reservations."""

    def __init__(
        self,
        total_cpu_cores: float = 16.0,
        total_memory_mb: float = 64000.0,
    ) -> None:
        self._lock = threading.RLock()
        self._total_cpu = total_cpu_cores
        self._total_memory = total_memory_mb
        # reservation_id -> ResourceReservation
        self._reservations: Dict[str, ResourceReservation] = {}
        # pipeline_id -> reservation_id
        self._pipeline_map: Dict[str, str] = {}

    def reserve_resources(
        self,
        pipeline_id: str,
        cpu_cores: float = 2.0,
        memory_mb: float = 4096.0,
    ) -> Optional[ResourceReservation]:
        """Attempt to reserve CPU and memory resources for a pipeline."""
        with self._lock:
            if pipeline_id in self._pipeline_map:
                # Already has reservation
                res_id = self._pipeline_map[pipeline_id]
                return self._reservations.get(res_id)

            allocated_cpu = sum(r.cpu_cores for r in self._reservations.values())
            allocated_mem = sum(r.memory_mb for r in self._reservations.values())

            if (allocated_cpu + cpu_cores > self._total_cpu) or (
                allocated_mem + memory_mb > self._total_memory
            ):
                logger.warning(
                    "Resource allocation failed for pipeline '%s': requested (cpu=%.1f, mem=%.1f), available (cpu=%.1f, mem=%.1f)",
                    pipeline_id, cpu_cores, memory_mb, self._total_cpu - allocated_cpu, self._total_memory - allocated_mem
                )
                return None

            reservation = ResourceReservation(
                pipeline_id=pipeline_id,
                cpu_cores=cpu_cores,
                memory_mb=memory_mb,
            )
            self._reservations[reservation.reservation_id] = reservation
            self._pipeline_map[pipeline_id] = reservation.reservation_id

            logger.info("Reserved resources for pipeline '%s' (cpu=%.1f, mem=%.1f)", pipeline_id, cpu_cores, memory_mb)
            return reservation

    def release_resources(self, identifier: str) -> bool:
        """Release reservation by reservation_id OR pipeline_id."""
        with self._lock:
            reservation_id = identifier
            if identifier in self._pipeline_map:
                reservation_id = self._pipeline_map[identifier]

            reservation = self._reservations.pop(reservation_id, None)
            if reservation is None:
                return False

            self._pipeline_map.pop(reservation.pipeline_id, None)
            logger.info("Released resources for pipeline '%s' (res_id=%s)", reservation.pipeline_id, reservation_id)
            return True

    def get_reservation(self, pipeline_id: str) -> Optional[ResourceReservation]:
        """Get current reservation for a pipeline."""
        with self._lock:
            res_id = self._pipeline_map.get(pipeline_id)
            if not res_id:
                return None
            return self._reservations.get(res_id)

    def available_resources(self) -> Dict[str, float]:
        """Get currently available unallocated capacity."""
        with self._lock:
            allocated_cpu = sum(r.cpu_cores for r in self._reservations.values())
            allocated_mem = sum(r.memory_mb for r in self._reservations.values())
            return {
                "available_cpu": max(0.0, self._total_cpu - allocated_cpu),
                "available_memory_mb": max(0.0, self._total_memory - allocated_mem),
                "total_cpu": self._total_cpu,
                "total_memory_mb": self._total_memory,
            }

    def clear(self) -> None:
        """Clear all active reservations."""
        with self._lock:
            self._reservations.clear()
            self._pipeline_map.clear()
