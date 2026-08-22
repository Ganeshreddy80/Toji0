"""Workflow Engine for executing reusable composite pipelines across the TOJI platform."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from orchestrators.events import AlertTriggered, WorkflowStepExecuted

if TYPE_CHECKING:
    from orchestrators.dashboard_orchestrator.dashboard import DashboardOrchestrator
    from orchestrators.learning_orchestrator.learning import LearningOrchestrator
    from orchestrators.market_orchestrator.market import MarketOrchestrator
    from orchestrators.research_orchestrator.research import ResearchOrchestrator
    from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Coordinates multi-step workflows, emitting pipeline progression events."""

    def __init__(
        self,
        event_bus: IEventBus,
        market_orch: MarketOrchestrator,
        research_orch: ResearchOrchestrator,
        learning_orch: LearningOrchestrator,
        dashboard_orch: DashboardOrchestrator,
    ) -> None:
        """Initialize the WorkflowEngine.

        Args:
            event_bus: Kernel Event Bus.
            market_orch: Market data pipeline orchestrator.
            research_orch: Research configuration orchestrator.
            learning_orch: Retrospect learning orchestrator.
            dashboard_orch: Live updates and stats tracking orchestrator.
        """
        self.event_bus = event_bus
        self.market_orch = market_orch
        self.research_orch = research_orch
        self.learning_orch = learning_orch
        self.dashboard_orch = dashboard_orch

    def _emit_step(self, wf_name: str, step_name: str, status: str = "success", result: dict[str, Any] | None = None) -> None:
        """Helper to dispatch step execution updates."""
        event = WorkflowStepExecuted(
            source="WorkflowEngine",
            payload={
                "workflow_name": wf_name,
                "step_name": step_name,
                "status": status,
                "result": result or {},
            }
        )
        self.event_bus.publish(event)

    # ── Workflow Definitions ───────────────────────────────────────────

    def execute_morning_briefing(self, symbols: list[str]) -> None:
        """Scan active assets, log initial pulses, send system alerts."""
        wf = "MorningBriefing"
        logger.info("Starting workflow: %s", wf)

        # Step 1: Initialize Scan alert
        self.event_bus.publish(
            AlertTriggered(
                source="WorkflowEngine",
                payload={"severity": "info", "message": f"Starting Morning Briefing for: {symbols}"}
            )
        )
        self._emit_step(wf, "alert_sent")

        # Step 2: Assemble pulse overview
        pulses = self.dashboard_orch.get_market_pulses()
        self._emit_step(wf, "compile_pulses", result={"active_pulse_count": len(pulses)})
        logger.info("Workflow completed: %s", wf)

    def execute_continuous_market_scan(
        self,
        symbols: list[str],
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Pull fresh bars for target symbols, triggering feature pipelines and committee votes."""
        wf = "ContinuousMarketScan"
        logger.info("Starting workflow: %s", wf)

        for sym in symbols:
            try:
                # Triggers: Ingestion -> validation -> features -> Event -> Decision -> timeline
                self.market_orch.process_market_data(sym, interval, start_time, end_time)
                self._emit_step(wf, f"process_market_{sym}", result={"symbol": sym, "status": "success"})
            except Exception as e:
                self._emit_step(wf, f"process_market_{sym}", status="failed", result={"error": str(e)})

        logger.info("Workflow completed: %s", wf)

    def execute_opportunity_ranking(self, opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Scoring, sorting, and alerting the trading dashboard."""
        wf = "OpportunityRanking"
        logger.info("Starting workflow: %s", wf)

        # Sort based on score descending
        sorted_opps = sorted(opportunities, key=lambda x: x.get("score", 0.0), reverse=True)
        
        # Trigger alert for top ranked item
        if sorted_opps:
            top = sorted_opps[0]
            self.event_bus.publish(
                AlertTriggered(
                    source="WorkflowEngine",
                    payload={
                        "severity": "warning",
                        "message": f"Top ranked opportunity detected: {top.get('symbol')} score={top.get('score')}",
                        "symbol": top.get("symbol"),
                    }
                )
            )

        self._emit_step(wf, "opportunities_sorted", result={"count": len(sorted_opps)})
        logger.info("Workflow completed: %s", wf)
        return sorted_opps

    def execute_decision_review(self) -> None:
        """Review created decisions and verify timeline registry audit trails."""
        wf = "DecisionReview"
        logger.info("Starting workflow: %s", wf)

        summary = self.dashboard_orch.get_performance_summary()
        self._emit_step(wf, "audit_timelines", result=summary)
        logger.info("Workflow completed: %s", wf)

    def execute_daily_learning(self, decision_prices: dict[str, list[float]]) -> None:
        """Audit past decisions, update outcome records, adapt rule weights."""
        wf = "DailyLearning"
        logger.info("Starting workflow: %s", wf)

        for dec_id, price_series in decision_prices.items():
            try:
                is_correct = self.learning_orch.audit_decision_performance(dec_id, price_series)
                self._emit_step(wf, f"audit_{dec_id}", result={"decision_id": dec_id, "correct": is_correct})
            except Exception as e:
                self._emit_step(wf, f"audit_{dec_id}", status="failed", result={"error": str(e)})

        logger.info("Workflow completed: %s", wf)

    def execute_end_of_day_report(self) -> str:
        """Compile aggregated markdown report summarizing daily decisions, accuracy, and lessons."""
        wf = "EndOfDayReport"
        logger.info("Starting workflow: %s", wf)

        summary = self.dashboard_orch.get_performance_summary()
        alerts = self.dashboard_orch.get_active_alerts()

        report_md = f"""# TOJI End of Day Performance Report
Generated at: {datetime.now(timezone.utc).isoformat()}

## Performance Summary
- Total Decisions: {summary.get('total_decisions')}
- Correct Decisions: {summary.get('correct_decisions')}
- Accuracy Ratio: {summary.get('correctness_ratio'):.2%}

## High Severity Alerts Dispatched
"""
        for a in alerts[-10:]:  # Last 10 alerts
            report_md += f"- [{a.get('severity').upper()}] {a.get('message')} ({a.get('timestamp')})\n"

        self._emit_step(wf, "report_compiled")
        logger.info("Workflow completed: %s", wf)
        return report_md
