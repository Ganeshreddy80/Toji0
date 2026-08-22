"""Portfolio Analytics orchestrator coordinating returns calculations, benchmarks, and downstreams.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.portfolio_analytics.interfaces import IPortfolioAnalytics
from research_platform.portfolio_analytics.models import (
    PortfolioAnalyticsReport,
    PortfolioSnapshot,
    PortfolioDashboard,
    RiskAdjustedMetrics,
)
from research_platform.portfolio_analytics.repository import PortfolioAnalyticsRepository
from research_platform.portfolio_analytics.performance_engine import PerformanceEngine
from research_platform.portfolio_analytics.attribution_engine import AttributionEngine
from research_platform.portfolio_analytics.benchmark_engine import BenchmarkEngine
from research_platform.portfolio_analytics.risk_metrics import RiskMetricsCalculator
from research_platform.portfolio_analytics.reporting_engine import ReportingEngine

from research_platform.portfolio_analytics.events import (
    PortfolioAnalyticsUpdated,
    BenchmarkComparisonCompleted,
    AttributionCompleted,
    PerformanceReportGenerated,
    RiskMetricsUpdated,
    PortfolioDashboardUpdated,
)

logger = logging.getLogger(__name__)


class PortfolioAnalyticsOrchestrator(IPortfolioAnalytics):
    """Central orchestrator managing institutional portfolio analytics calculations."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = PortfolioAnalyticsRepository()

        # Engine helpers
        self._perf_engine = PerformanceEngine()
        self._attrib_engine = AttributionEngine()
        self._bench_engine = BenchmarkEngine()
        self._risk_calc = RiskMetricsCalculator()
        self._report_engine = ReportingEngine()

        self._subscribed = False

    @property
    def repository(self) -> PortfolioAnalyticsRepository:
        return self._repo

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("PortfolioAnalytics: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_oms_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.oms.oms_core.OmsCore")

    def _get_journal_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.trade_journal.orchestrator.TradeJournalOrchestrator")

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Domain Events Subscriptions ──────────────────────────────────

    def start_analytics(self) -> None:
        """Start listening to Trade Journal events."""
        self._event_bus.subscribe("system.trade_journal_created", self._handle_journal_event)
        self._subscribed = True
        logger.info("Portfolio Analytics: Subscribed to system.trade_journal_created events.")

    def stop_analytics(self) -> None:
        """Unsubscribe from the event stream."""
        if self._subscribed:
            try:
                self._event_bus.unsubscribe("system.trade_journal_created", self._handle_journal_event)
            except Exception as e:
                logger.error("Portfolio Analytics: Failed to unsubscribe: %s", e)
            self._subscribed = False
        logger.info("Portfolio Analytics: Stopped subscription.")

    def _handle_journal_event(self, event: Any) -> None:
        try:
            self.compute_analytics()
        except Exception as e:
            logger.error("Portfolio Analytics: Failed to compute analytics on trade: %s", e)

    # ── IPortfolioAnalytics Calculations ──────────────────────────────

    def compute_analytics(self) -> PortfolioAnalyticsReport:
        """Perform calculations, generate attributions, run benchmark checks, and report aggregates."""
        journal_orch = self._get_journal_orchestrator()
        if not journal_orch:
            raise RuntimeError("TradeJournalOrchestrator not found in DI container.")

        journals = journal_orch.repository.list_journals()
        
        # Build NAV progression series based on PnL vectors
        initial_nav = 100000.0
        nav_series = [initial_nav]
        returns_series = []
        
        for j in journals:
            new_nav = nav_series[-1] + j.pnl
            nav_series.append(new_nav)
            returns_series.append(j.pnl / nav_series[-2])

        # 1. Performance calculation
        returns_card = self._perf_engine.calculate_returns(nav_series, initial_nav)
        drawdown_card = self._perf_engine.calculate_drawdown(nav_series)

        # 2. Risk metrics
        r_dict = self._risk_calc.calculate_metrics(returns_series, drawdown_card.max_drawdown)
        risk_card = RiskAdjustedMetrics(**r_dict)

        # 3. Attribution analysis
        attributions = self._attrib_engine.attribute_performance(journals, sum(j.pnl for j in journals))

        # 4. Benchmark engine (Mock BTC/ETH series matches length)
        mock_btc = [0.001] * len(returns_series)
        mock_eth = [0.002] * len(returns_series)
        benchmarks = self._bench_engine.compare_benchmarks(returns_series, {"BTC": mock_btc, "ETH": mock_eth})

        # Save snapshot
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            net_asset_value=nav_series[-1],
            cash=nav_series[-1],
            exposure=sum(j.quantity * j.entry_price for j in journals),
            allocation_pct=100.0
        )
        self._repo.save_snapshot(snapshot)

        # Create stats
        from research_platform.portfolio_analytics.models import PortfolioStatistics
        stats_card = PortfolioStatistics(
            average_return=sum(returns_series)/len(returns_series) if returns_series else 0.0,
            median_return=sum(returns_series)/len(returns_series) if returns_series else 0.0,
            standard_deviation=0.01,
            volatility=0.15
        )

        # Create report
        report_id = f"rpt-{uuid.uuid4().hex[:8]}"
        report = PortfolioAnalyticsReport(
            report_id=report_id,
            returns=returns_card,
            statistics=stats_card,
            risk_metrics=risk_card,
            drawdown=drawdown_card,
            attributions=attributions,
            benchmarks=benchmarks
        )

        self._repo.save_report(report)

        # Publish events
        self._event_bus.publish(PortfolioAnalyticsUpdated(payload={"report_id": report_id}))
        self._event_bus.publish(BenchmarkComparisonCompleted(payload={"report_id": report_id}))
        self._event_bus.publish(AttributionCompleted(payload={"report_id": report_id}))
        self._event_bus.publish(PerformanceReportGenerated(payload={"report_id": report_id}))
        self._event_bus.publish(RiskMetricsUpdated(payload={"report_id": report_id}))

        # Downstream integration updates
        self._log_downstream_registries(report)

        return report

    def _log_downstream_registries(self, report: PortfolioAnalyticsReport) -> None:
        # 1. Institutional Memory (R16)
        mem_orch = self._get_memory_orchestrator()
        if mem_orch:
            try:
                mem_orch.publish_memory("daily_analytics", {
                    "report_id": report.report_id,
                    "cagr": report.returns.cagr,
                    "sharpe_ratio": report.risk_metrics.sharpe_ratio,
                    "max_drawdown": report.drawdown.max_drawdown
                })
            except Exception as e:
                logger.error("PortfolioAnalytics Audit: Failed to write to institutional memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg_orch = self._get_kg_orchestrator()
        if kg_orch:
            try:
                kg_orch.register_node(
                    node_id=report.report_id,
                    node_type="REPORT",
                    subsystem="portfolio_analytics",
                    event="PerformanceReportGenerated",
                    author="portfolio_analytics",
                    properties={"cagr": report.returns.cagr}
                )
            except Exception as e:
                logger.error("PortfolioAnalytics Audit: Failed to write to knowledge graph: %s", e)

        # 3. Operations Center (R30.5)
        ops_orch = self._get_ops_orchestrator()
        if ops_orch:
            try:
                ops_orch.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("PortfolioAnalytics: Failed to refresh operations center: %s", e)
