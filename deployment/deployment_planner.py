"""Thread-safe Deployment Planner generating dry-run rollout and rollback plans (Sprint 12B)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from deployment.deployment_config import DeploymentConfig
from deployment.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class DeploymentPlan(BaseModel):
    """Immutable dry-run deployment plan representation."""

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_service: str = Field(..., description="Target service name.")
    version: str = Field(..., description="Target version.")
    dependency_order: List[str] = Field(default_factory=list, description="Topological deployment sequence.")
    rollout_stages: List[Dict[str, Any]] = Field(default_factory=list, description="Rollout stage definitions.")
    rollback_plan: Dict[str, Any] = Field(default_factory=dict, description="Rollback instructions.")
    is_dry_run: bool = Field(default=True)
    is_advisory_only: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class DeploymentPlanner:
    """Generates dry-run deployment plans, rollout stages, and rollback strategies."""

    def generate_plan(
        self,
        service_name: str,
        version: str,
        config: DeploymentConfig,
        registry: ServiceRegistry,
    ) -> DeploymentPlan:
        """Generate dry-run rollout and rollback plan without executing any deployment."""
        # Step 1: Topological dependency resolution
        dep_order = registry.resolve_dependency_order(service_name)

        # Step 2: Build stage progression
        stages: List[Dict[str, Any]] = [
            {
                "stage": 1,
                "name": "Dependency Verification",
                "target_services": dep_order[:-1] if len(dep_order) > 1 else [],
                "traffic_pct": 0,
            },
            {
                "stage": 2,
                "name": f"{config.deployment_strategy.value.capitalize()} Initial Canary",
                "target_services": [service_name],
                "traffic_pct": 10 if config.deployment_strategy.value == "canary" else 25,
                "replicas": max(1, config.replica_count // 4),
            },
            {
                "stage": 3,
                "name": "Full Production Scale",
                "target_services": [service_name],
                "traffic_pct": 100,
                "replicas": config.replica_count,
            },
        ]

        # Step 3: Build rollback plan instructions
        rollback = {
            "strategy": "automatic_revert",
            "previous_version": "auto_detect",
            "drain_timeout_sec": 30,
            "actions": [
                f"Stop new replicas for {service_name}",
                f"Re-route traffic to previous stable version",
                "Emit failure alarm to CloudWatch",
            ],
        }

        plan = DeploymentPlan(
            target_service=service_name,
            version=version,
            dependency_order=dep_order,
            rollout_stages=stages,
            rollback_plan=rollback,
        )

        logger.info("Generated dry-run deployment plan '%s' for '%s' v%s", plan.plan_id, service_name, version)
        return plan
