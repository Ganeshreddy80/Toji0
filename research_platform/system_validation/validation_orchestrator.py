"""Validation orchestrator coordinating the entire TOJI validation suite.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.system_validation.interfaces import IValidationOrchestrator
from research_platform.system_validation.models import (
    SubsystemHealth,
    SystemCertificationCard,
)
from research_platform.system_validation.validation_repository import ValidationRepository
from research_platform.system_validation.performance_snapshot import PerformanceSnapshot
from research_platform.system_validation.certification import CertificationEngine
from research_platform.system_validation.events import (
    PlatformCertified,
    SubsystemValidated,
    ValidationStarted,
)

# Core Validators
from research_platform.system_validation.dependency_validator import DependencyValidator
from research_platform.system_validation.plugin_validator import PluginValidator
from research_platform.system_validation.repository_validator import RepositoryValidator
from research_platform.system_validation.event_bus_validator import EventBusValidator
from research_platform.system_validation.workflow_validator import WorkflowValidator
from research_platform.system_validation.integration_validator import IntegrationValidator
from research_platform.system_validation.memory_validator import MemoryValidator
from research_platform.system_validation.knowledge_graph_validator import KnowledgeGraphValidator
from research_platform.system_validation.ai_validator import AiValidator
from research_platform.system_validation.risk_validator import RiskValidator
from research_platform.system_validation.execution_validator import ExecutionValidator
from research_platform.system_validation.simulation_validator import SimulationValidator
from research_platform.system_validation.observability_validator import ObservabilityValidator
from research_platform.system_validation.market_validator import MarketValidator
from research_platform.system_validation.strategy_validator import StrategyValidator

logger = logging.getLogger(__name__)


class ValidationOrchestrator(IValidationOrchestrator):
    """Central manager executing all validator checks and outputting performance snap metrics."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = ValidationRepository()

        # Engines
        self._certifier = CertificationEngine()

        # Instantiate validators list
        self._validators = [
            DependencyValidator(),
            PluginValidator(),
            RepositoryValidator(),
            EventBusValidator(),
            WorkflowValidator(),
            IntegrationValidator(),
            MemoryValidator(),
            KnowledgeGraphValidator(),
            AiValidator(),
            RiskValidator(),
            ExecutionValidator(),
            SimulationValidator(),
            ObservabilityValidator(),
            MarketValidator(),
            StrategyValidator()
        ]

    @property
    def repository(self) -> ValidationRepository:
        return self._repo

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, cert: SystemCertificationCard) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            cert_node_id = f"cert-{cert.block_hash[:8]}"
            kg_orch.register_node(
                node_id=cert_node_id,
                node_type="CERTIFICATION_RUN",
                subsystem="system_validation",
                event="PlatformCertified",
                author="system",
                properties={"status": cert.status, "score": cert.overall_score}
            )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def execute_validation_suite(self) -> SystemCertificationCard:
        """Execute all validators, measure resource snapshots, and certify TOJI."""
        t_start = time.perf_counter()
        self._event_bus.publish(ValidationStarted(payload={"timestamp": datetime_now_iso()}))

        health_cards: List[SubsystemHealth] = []

        for val in self._validators:
            card = val.validate(self._container)
            self._repo.save_health(card)
            self._event_bus.publish(SubsystemValidated(payload={
                "subsystem": card.name,
                "score": card.score
            }))
            health_cards.append(card)

        # Certify scorecards
        cert = self._certifier.certify(health_cards)
        self._repo.save_certification(cert)
        self._event_bus.publish(PlatformCertified(payload={
            "status": cert.status,
            "overall_score": cert.overall_score
        }))

        # Snap usage
        snap = PerformanceSnapshot.capture(t_start)

        # Downstream logging integrations
        self._publish_memory_record("system_certifications", cert)
        self._publish_memory_record("validation_snapshots", snap)
        self._update_knowledge_graph(cert)

        logger.info("TOJI validation suite executed in %.4f sec. Status: %s, Score: %.2f",
                    snap.validation_duration, cert.status, cert.overall_score)

        return cert


def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
