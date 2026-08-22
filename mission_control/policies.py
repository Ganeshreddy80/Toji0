"""Immutable Operational Automation Policies for Mission Control (Sprint 10C)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AutoRestartPolicy(BaseModel):
    """Immutable policy governing automatic service restarts."""

    enabled: bool = Field(default=True, description="Whether automatic restarting is enabled.")
    max_restarts: int = Field(default=3, ge=1, description="Maximum restarts permitted within window.")
    window_seconds: float = Field(default=3600.0, ge=1.0, description="Time window in seconds for restart count.")
    cooldown_seconds: float = Field(default=10.0, ge=0.0, description="Delay between restart attempts.")

    model_config = ConfigDict(frozen=True)


class RecoveryPolicy(BaseModel):
    """Immutable policy governing automated service recovery attempts."""

    enabled: bool = Field(default=True, description="Whether automated recovery is enabled.")
    max_retries: int = Field(default=3, ge=1, description="Maximum recovery retry attempts.")
    retry_delay_seconds: float = Field(default=5.0, ge=0.0, description="Delay between recovery attempts.")
    auto_recover_degraded: bool = Field(default=True, description="Auto recover DEGRADED services.")

    model_config = ConfigDict(frozen=True)


class EscalationPolicy(BaseModel):
    """Immutable policy governing automated incident escalation."""

    enabled: bool = Field(default=True, description="Whether automated escalation is enabled.")
    auto_escalate_on_max_restarts: bool = Field(default=True, description="Escalate when restart limit exceeded.")
    auto_escalate_on_dependency_failure: bool = Field(default=True, description="Escalate when upstream dependency fails.")
    max_failures_before_escalation: int = Field(default=3, ge=1, description="Failure count threshold for escalation.")

    model_config = ConfigDict(frozen=True)


class MaintenancePolicy(BaseModel):
    """Immutable policy governing behavior during scheduled maintenance."""

    enabled: bool = Field(default=True, description="Whether maintenance policy rules apply.")
    allow_auto_recovery_during_maintenance: bool = Field(default=False, description="Allow recovery in maintenance window.")
    suppress_alerts_during_maintenance: bool = Field(default=True, description="Suppress alerts during maintenance.")

    model_config = ConfigDict(frozen=True)
