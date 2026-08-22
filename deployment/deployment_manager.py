"""Thread-safe Deployment Manager orchestrating container deployment lifecycle (Sprint 12B)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from deployment.container_runtime import MockContainerRuntime
from deployment.deployment_config import DeploymentConfig
from deployment.deployment_descriptor import DeploymentDescriptor, DeploymentStatus
from deployment.deployment_events import (
    DeploymentApproved,
    DeploymentArchived,
    DeploymentCancelled,
    DeploymentCreated,
    DeploymentValidated,
    HealthStatusUpdated,
    RuntimeOperationPerformed,
    ServiceRegistered,
)
from deployment.deployment_planner import DeploymentPlan, DeploymentPlanner
from deployment.deployment_validator import DeploymentValidator, ValidationReport
from deployment.health_monitor import HealthMonitor, ServiceHealthRecord
from deployment.service_registry import ServiceRecord, ServiceRegistry
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class DeploymentManager:
    """Thread-safe Deployment Manager orchestrating planning, validation, registry, container runtime, and health monitoring."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        planner: Optional[DeploymentPlanner] = None,
        validator: Optional[DeploymentValidator] = None,
        registry: Optional[ServiceRegistry] = None,
        runtime: Optional[MockContainerRuntime] = None,
        health_monitor: Optional[HealthMonitor] = None,
        max_deployments: int = 5000,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._planner = planner or DeploymentPlanner()
        self._validator = validator or DeploymentValidator()
        self._registry = registry or ServiceRegistry()
        self._runtime = runtime or MockContainerRuntime()
        self._health_monitor = health_monitor or HealthMonitor()
        self._max_deployments = max_deployments

        # deployment_id -> DeploymentDescriptor
        self._deployments: Dict[str, DeploymentDescriptor] = {}

    def create_deployment(
        self,
        service_name: str,
        version: str = "1.0.0",
        config: Optional[DeploymentConfig] = None,
    ) -> DeploymentDescriptor:
        """Create a new advisory deployment record and generate its dry-run plan."""
        with self._lock:
            if len(self._deployments) >= self._max_deployments:
                oldest_id = next(iter(self._deployments))
                del self._deployments[oldest_id]

            cfg = config or DeploymentConfig()

            # Ensure service is registered in registry
            if not self._registry.get_service(service_name):
                self.register_service(service_name, version)

            # Generate dry-run plan
            plan = self._planner.generate_plan(service_name, version, cfg, self._registry)

            descriptor = DeploymentDescriptor(
                service_name=service_name,
                version=version,
                environment=cfg.environment.value,
                status=DeploymentStatus.CREATED,
                config=cfg,
                plan_summary={
                    "plan_id": plan.plan_id,
                    "dependency_order": plan.dependency_order,
                    "stages_count": len(plan.rollout_stages),
                },
            )

            self._deployments[descriptor.deployment_id] = descriptor
            logger.info("Created deployment '%s' for service '%s' v%s", descriptor.deployment_id, service_name, version)

            if self._event_bus:
                self._event_bus.publish(
                    DeploymentCreated(
                        deployment_id=descriptor.deployment_id,
                        service_name=service_name,
                        environment=cfg.environment.value,
                    )
                )
            return descriptor

    def validate_deployment(self, deployment_id: str) -> ValidationReport:
        """Validate an existing deployment and transition status to VALIDATED if clean."""
        with self._lock:
            desc = self._get_deployment_or_raise(deployment_id)

            active_services = [
                d.service_name for d in self._deployments.values() if d.status == DeploymentStatus.APPROVED
            ]
            report = self._validator.validate(desc.service_name, desc.config, self._registry, active_services)

            if report.is_valid and desc.status == DeploymentStatus.CREATED:
                validated_desc = DeploymentDescriptor(
                    deployment_id=desc.deployment_id,
                    service_name=desc.service_name,
                    version=desc.version,
                    environment=desc.environment,
                    status=DeploymentStatus.VALIDATED,
                    config=desc.config,
                    plan_summary=desc.plan_summary,
                    created_at=desc.created_at,
                    validated_at=datetime.now(timezone.utc),
                )
                self._deployments[deployment_id] = validated_desc

            if self._event_bus:
                self._event_bus.publish(
                    DeploymentValidated(
                        deployment_id=deployment_id,
                        is_valid=report.is_valid,
                        error_count=len(report.errors),
                    )
                )
            return report

    def approve_deployment(self, deployment_id: str, approver: str = "advisory_system") -> DeploymentDescriptor:
        """Approve a validated deployment (advisory-only approval)."""
        with self._lock:
            desc = self._get_deployment_or_raise(deployment_id)

            if desc.status in (DeploymentStatus.CANCELLED, DeploymentStatus.ARCHIVED):
                return desc

            approved_desc = DeploymentDescriptor(
                deployment_id=desc.deployment_id,
                service_name=desc.service_name,
                version=desc.version,
                environment=desc.environment,
                status=DeploymentStatus.APPROVED,
                config=desc.config,
                plan_summary=desc.plan_summary,
                created_at=desc.created_at,
                validated_at=desc.validated_at,
                approved_at=datetime.now(timezone.utc),
            )
            self._deployments[deployment_id] = approved_desc

            # Simulate mock container creation & start
            container = self._runtime.create_container(
                name=f"{desc.service_name}-{desc.deployment_id[:8]}",
                image=f"toji/{desc.service_name}:{desc.version}",
                env_vars=desc.config.env_variables,
            )
            self._runtime.start_container(container.container_id)

            if self._event_bus:
                self._event_bus.publish(
                    RuntimeOperationPerformed(
                        operation="start_container",
                        container_id=container.container_id,
                        status="RUNNING",
                    )
                )
                self._event_bus.publish(
                    DeploymentApproved(
                        deployment_id=deployment_id,
                        approver=approver,
                    )
                )

            return approved_desc

    def cancel_deployment(self, deployment_id: str, reason: str = "User cancelled") -> DeploymentDescriptor:
        """Cancel an active or pending deployment."""
        with self._lock:
            desc = self._get_deployment_or_raise(deployment_id)

            if desc.status in (DeploymentStatus.CANCELLED, DeploymentStatus.ARCHIVED):
                return desc

            cancelled_desc = DeploymentDescriptor(
                deployment_id=desc.deployment_id,
                service_name=desc.service_name,
                version=desc.version,
                environment=desc.environment,
                status=DeploymentStatus.CANCELLED,
                config=desc.config,
                plan_summary=desc.plan_summary,
                error_message=f"Cancelled: {reason}",
                created_at=desc.created_at,
                validated_at=desc.validated_at,
                approved_at=desc.approved_at,
            )
            self._deployments[deployment_id] = cancelled_desc

            if self._event_bus:
                self._event_bus.publish(
                    DeploymentCancelled(
                        deployment_id=deployment_id,
                        reason=reason,
                    )
                )
            return cancelled_desc

    def archive_deployment(self, deployment_id: str) -> DeploymentDescriptor:
        """Archive a cancelled or completed deployment."""
        with self._lock:
            desc = self._get_deployment_or_raise(deployment_id)

            if desc.status == DeploymentStatus.ARCHIVED:
                return desc

            archived_desc = DeploymentDescriptor(
                deployment_id=desc.deployment_id,
                service_name=desc.service_name,
                version=desc.version,
                environment=desc.environment,
                status=DeploymentStatus.ARCHIVED,
                config=desc.config,
                plan_summary=desc.plan_summary,
                error_message=desc.error_message,
                created_at=desc.created_at,
                validated_at=desc.validated_at,
                approved_at=desc.approved_at,
                archived_at=datetime.now(timezone.utc),
            )
            self._deployments[deployment_id] = archived_desc

            if self._event_bus:
                self._event_bus.publish(
                    DeploymentArchived(
                        deployment_id=deployment_id,
                    )
                )
            return archived_desc

    def register_service(
        self,
        service_name: str,
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
    ) -> ServiceRecord:
        """Register a service in the registry and publish event."""
        with self._lock:
            rec = self._registry.register_service(service_name, version, dependencies)
            if self._event_bus:
                self._event_bus.publish(
                    ServiceRegistered(
                        service_name=service_name,
                        version=version,
                    )
                )
            return rec

    def record_health_heartbeat(
        self,
        service_name: str,
        is_alive: bool = True,
        is_ready: bool = True,
        status_message: str = "Healthy",
    ) -> ServiceHealthRecord:
        """Record health heartbeat and publish event."""
        with self._lock:
            rec = self._health_monitor.record_heartbeat(service_name, is_alive, is_ready, status_message)
            if self._event_bus:
                self._event_bus.publish(
                    HealthStatusUpdated(
                        service_name=service_name,
                        is_alive=is_alive,
                        is_ready=is_ready,
                    )
                )
            return rec

    def get_deployment(self, deployment_id: str) -> Optional[DeploymentDescriptor]:
        """Lookup deployment by ID."""
        with self._lock:
            return self._deployments.get(deployment_id)

    def list_deployments(self, status: Optional[DeploymentStatus] = None) -> List[DeploymentDescriptor]:
        """List deployment descriptors, optionally filtered by status."""
        with self._lock:
            records = list(self._deployments.values())
            if status:
                records = [r for r in records if r.status == status]
            return records

    def _get_deployment_or_raise(self, deployment_id: str) -> DeploymentDescriptor:
        desc = self._deployments.get(deployment_id)
        if not desc:
            raise ValueError(f"Deployment '{deployment_id}' not found")
        return desc

    # Sub-component accessors
    @property
    def planner(self) -> DeploymentPlanner:
        return self._planner

    @property
    def validator(self) -> DeploymentValidator:
        return self._validator

    @property
    def registry(self) -> ServiceRegistry:
        return self._registry

    @property
    def runtime(self) -> MockContainerRuntime:
        return self._runtime

    @property
    def health_monitor(self) -> HealthMonitor:
        return self._health_monitor

    def count(self) -> int:
        """Return total count of managed deployments."""
        with self._lock:
            return len(self._deployments)

    def clear(self) -> None:
        """Clear state across all managed deployment sub-components."""
        with self._lock:
            self._deployments.clear()
            self._registry.clear()
            self._runtime.clear()
            self._health_monitor.clear()
