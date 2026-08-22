"""Decision Orchestrator for compiling committee votes, running consensus, and logging decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from toji_platform.core.event_bus.events import DecisionGenerated

if TYPE_CHECKING:
    from decision.explainability.engine import ExplainabilityEngine
    from decision.journal.manager import DecisionJournal
    from decision.voting.engine import InvestmentCommittee
    from toji_platform.core.event_bus.interfaces import IEvent
    from toji_platform.core.event_bus.interfaces import IEventBus


class DecisionOrchestrator:
    """Listens to market updates, runs committee votes, compiles consensus, and archives decisions."""

    def __init__(
        self,
        event_bus: IEventBus,
        investment_committee: InvestmentCommittee,
        decision_journal: DecisionJournal,
        explainability_engine: ExplainabilityEngine,
    ) -> None:
        """Initialize the DecisionOrchestrator.

        Args:
            event_bus: Kernel Event Bus.
            investment_committee: Voted consensus InvestmentCommittee engine.
            decision_journal: Decoupled DecisionJournal registry.
            explainability_engine: Markdown report compiler.
        """
        self.event_bus = event_bus
        self.investment_committee = investment_committee
        self.decision_journal = decision_journal
        self.explainability_engine = explainability_engine

        # Subscribe to market data updates
        self.event_bus.subscribe("system.market_data_updated", self.handle_market_data_updated)

    def handle_market_data_updated(self, event: IEvent) -> None:
        """Listen to market data arrival, aggregate context, run voting, and publish decisions."""
        payload = event.payload
        symbol = payload.get("symbol")
        if not symbol:
            return

        # 1. Compile integrated context from event and default fallback parameters
        prices = payload.get("prices", [100.0])
        volumes = payload.get("volumes", [1.0])

        context = {
            # Research
            "win_rate": payload.get("win_rate", 0.60),
            "sharpe": payload.get("sharpe", 2.2),
            "p_value": payload.get("p_value", 0.01),
            "t_stat": payload.get("t_stat", 2.8),
            "experiment_validation": payload.get("experiment_validation", "passed"),
            "backtest_robustness_score": payload.get("backtest_robustness_score", 0.85),
            # Risk
            "returns": [float(p1 - p2) / p2 for p1, p2 in zip(prices[1:], prices[:-1])] if len(prices) > 1 else [0.0],
            "equity_series": prices,
            "positions_value": payload.get("positions_value", {symbol: 1000.0}),
            "total_equity": payload.get("total_equity", 100000.0),
            "payoff_ratio": payload.get("payoff_ratio", 1.8),
            "fraction_risked": payload.get("fraction_risked", 0.02),
            "gross_exposure": payload.get("gross_exposure", 1.1),
            # Portfolio
            "concentration_pct": payload.get("concentration_pct", 0.05),
            "average_correlation": payload.get("average_correlation", 0.15),
            "suggested_allocation_pct": payload.get("suggested_allocation_pct", 0.05),
            # Timing
            "timing_window": payload.get("timing_window", "Immediate"),
            "signal_age_seconds": payload.get("signal_age_seconds", 12.0),
            "event_proximity_seconds": payload.get("event_proximity_seconds", 7200.0),
            "regime_aligned": payload.get("regime_aligned", True),
            "session": payload.get("session", "New York"),
            # Knowledge
            "rule_confidence_weight": payload.get("rule_confidence_weight", 0.80),
            "evidence_count": payload.get("evidence_count", 4),
            "active_contradictions_count": payload.get("active_contradictions_count", 0),
            "knowledge_freshness": payload.get("knowledge_freshness", 0.90),
            # General links
            "supporting_evidence": payload.get("supporting_evidence", ["empirical-1"]),
            "contradicting_evidence": payload.get("contradicting_evidence", []),
            "rule_references": payload.get("rule_references", ["rule-1"]),
            "research_references": payload.get("research_references", ["exp-run-1"]),
            "expiry_seconds": payload.get("expiry_seconds", 7200),
            "review_seconds": payload.get("review_seconds", 1800),
        }

        # 2. Invoke consensus compiler
        regime = payload.get("regime", "default")
        decision = self.investment_committee.compile_decision(
            symbol=symbol,
            context=context,
            regime=regime,
            evaluation_time=event.timestamp,
        )

        # 3. Compile audit reports
        report_md = self.explainability_engine.generate_explanation_report(decision)

        # 4. Log to journal
        self.decision_journal.log_decision(decision)

        # 5. Broadcast DecisionGenerated event
        decision_payload = {
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "overall_score": decision.overall_score,
            "recommendation": decision.final_recommendation.value,
            "confidence": decision.confidence,
            "report_md": report_md,
            "expiry_time": decision.expiry_time.isoformat(),
            "created_at": decision.created_at.isoformat(),
        }
        out_event = DecisionGenerated(
            source="DecisionOrchestrator", payload=decision_payload
        )
        self.event_bus.publish(out_event)
