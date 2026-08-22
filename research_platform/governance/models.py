"""Immutable Pydantic models for the Governance & Audit Platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AccessRole(str, Enum):
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    RISK_MANAGER = "RISK_MANAGER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    QUANT_RESEARCHER = "QUANT_RESEARCHER"


class ComplianceRule(BaseModel):
    """A compliance restriction rule verifying parameter ranges or drawdown limits."""

    rule_id: str
    name: str
    description: str
    criterion_key: str
    operator: str  # e.g., ">", "<", "==", ">="
    threshold: float
    severity: str = "HIGH"

    model_config = ConfigDict(frozen=True)


class PolicyEvaluationResult(BaseModel):
    """The scorecard outcome details of a policy checklist audit run."""

    rule_id: str
    passed: bool
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class DigitalSignature(BaseModel):
    """Cryptographic authorization token logging authority and matching keys."""

    author: str
    public_key_hash: str
    signature: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class DeploymentApproval(BaseModel):
    """The logged authorization register tracking active compliance rules."""

    approval_id: str
    deployment_id: str
    signatures: List[DigitalSignature] = Field(default_factory=list)
    policy_results: List[PolicyEvaluationResult] = Field(default_factory=list)
    status: str = "PENDING"  # APPROVED, REJECTED, PENDING
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class GovernanceAuditRecord(BaseModel):
    """A blockchain-linked audit record containing signed hashes of governance operations."""

    record_id: str
    action_type: str
    user_role: AccessRole
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature: Optional[DigitalSignature] = None
    policy_results: List[PolicyEvaluationResult] = Field(default_factory=list)
    block_hash: str
    previous_block_hash: str

    model_config = ConfigDict(frozen=True)
