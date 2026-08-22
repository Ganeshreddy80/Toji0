"""Institutional Reporting orchestrator coordinating daily, weekly, monthly report exports.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.reporting.models import ReportCard
from research_platform.reporting.repository import ReportingRepository
from research_platform.reporting.pdf_export import PdfExporter
from research_platform.reporting.json_export import JsonExporter
from research_platform.reporting.markdown_export import MarkdownExporter
from research_platform.reporting.events import ReportGenerated

logger = logging.getLogger(__name__)


class ReportingOrchestrator:
    """Central orchestrator managing daily, weekly, and monthly PDF/JSON exports."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = ReportingRepository()
        self._pdf = PdfExporter()
        self._json = JsonExporter()
        self._markdown = MarkdownExporter()

    @property
    def repository(self) -> ReportingRepository:
        return self._repo

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("Reporting: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def generate_report(self, report_id: str, title: str, content: str, format_type: str) -> ReportCard:
        # Format content based on target type
        if format_type == "PDF":
            formatted = self._pdf.format_pdf(title, content)
        elif format_type == "JSON":
            formatted = self._json.format_json(title, content)
        else:
            formatted = self._markdown.format_markdown(title, content)

        card = ReportCard(
            report_id=report_id,
            title=title,
            content=formatted,
            format_type=format_type
        )
        self._repo.save_report(card)
        
        self._event_bus.publish(ReportGenerated(payload={"report_id": report_id}))
        self._log_downstream_registries(report_id, "INSTITUTIONAL_REPORT", f"Report Generated: format_type={format_type}")
        return card

    def _log_downstream_registries(self, ref_id: str, element_type: str, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("observability", {
                    "ref_id": ref_id,
                    "type": element_type,
                    "message": message
                })
            except Exception as e:
                logger.error("Reporting Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="reporting",
                    event="ReportUpdated",
                    author="reporting",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("Reporting Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("Reporting: Failed to refresh operations center: %s", e)
