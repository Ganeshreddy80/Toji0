"""Thread-safe Deployment Validator generating advisory validation reports (Sprint 12B)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from deployment.deployment_config import DeploymentConfig
from deployment.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class ValidationReport(BaseModel):
    """Immutable validation report detailing errors and warnings."""

    is_valid: bool = Field(..., description="True if configuration and dependencies are valid.")
    errors: List[str] = Field(default_factory=list, description="Validation failure reasons.")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking warning messages.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class DeploymentValidator:
    """Validates deployment specifications against configuration limits and dependency graphs."""

    def validate(
        self,
        service_name: str,
        config: DeploymentConfig,
        registry: ServiceRegistry,
        active_services: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Perform comprehensive validation checks and return a ValidationReport."""
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Resource Limits Validation
        if config.cpu_allocation > config.max_cpu_limit:
            errors.append(f"CPU allocation {config.cpu_allocation} exceeds maximum allowed limit {config.max_cpu_limit}")

        if config.memory_allocation_mb > config.max_memory_limit_mb:
            errors.append(
                f"Memory allocation {config.memory_allocation_mb} MB exceeds maximum limit {config.max_memory_limit_mb} MB"
            )

        if config.replica_count > 100:
            warnings.append(f"High replica count requested ({config.replica_count}). Ensure cluster capacity.")

        # 2. Dependency Verification
        service_rec = registry.get_service(service_name)
        if not service_rec:
            warnings.append(f"Target service '{service_name}' not yet registered in ServiceRegistry.")
        else:
            for dep in service_rec.dependencies:
                if not registry.get_service(dep):
                    errors.append(f"Required dependency '{dep}' is not registered in ServiceRegistry.")

        # 3. Duplicate Active Deployment Check
        if active_services and service_name in active_services:
            warnings.append(f"Service '{service_name}' already has an active deployment in progress.")

        # 4. Strategy Compatibility
        if config.deployment_strategy.value == "canary" and config.replica_count < 2:
            warnings.append("Canary deployment strategy recommends replica_count >= 2 for traffic split.")

        is_valid = len(errors) == 0
        logger.info("Validation complete for '%s': is_valid=%s (%d errors, %d warnings)", service_name, is_valid, len(errors), len(warnings))

        return ValidationReport(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )
