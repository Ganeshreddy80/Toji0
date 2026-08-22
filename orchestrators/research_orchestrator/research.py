"""Research Orchestrator for experiment execution, validation, paper generation, and knowledge creation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from toji_platform.core.event_bus.events import ResearchCompleted
from research.experiments.models import ExperimentStatus
from research.papers.generator import PaperGenerator

if TYPE_CHECKING:
    from belief.engine import BeliefEngine  # type: ignore[import-not-found]
    from knowledge.beliefs.engine import BeliefEngine as KBeliefEngine
    from knowledge.evidence.engine import EvidenceEngine
    from knowledge.rules.engine import RuleEngine
    from toji_platform.core.event_bus.interfaces import IEventBus
    from research.experiments.manager import ExperimentManager


class ResearchOrchestrator:
    """Coordinates the full pipeline from raw quant experiments to active platform rules/beliefs."""

    def __init__(
        self,
        event_bus: IEventBus,
        experiment_manager: ExperimentManager,
        evidence_engine: EvidenceEngine,
        rule_engine: RuleEngine,
        belief_engine: KBeliefEngine,
        paper_generator: PaperGenerator | None = None,
    ) -> None:
        """Initialize the ResearchOrchestrator.

        Args:
            event_bus: Kernel Event Bus.
            experiment_manager: Experiment and run manager.
            evidence_engine: Knowledge Engine evidence registry.
            rule_engine: Knowledge Engine rule engine.
            belief_engine: Knowledge Engine belief engine.
            paper_generator: Markdown paper compiler.
        """
        self.event_bus = event_bus
        self.experiment_manager = experiment_manager
        self.evidence_engine = evidence_engine
        self.rule_engine = rule_engine
        self.belief_engine = belief_engine
        self.paper_generator = paper_generator or PaperGenerator()

    def execute_experiment_pipeline(
        self,
        name: str,
        description: str,
        dataset_ref: str,
        asset_universe: list[str],
        feature_refs: list[str],
        metrics: dict[str, float],
        rule_expression: str,
        belief_claim: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute a full research cycle: create config, run, compile paper, and register knowledge rules.

        Args:
            name: Experiment title.
            description: Underlying hypothesis description.
            dataset_ref: Historical data source reference.
            asset_universe: List of tradable assets under review.
            feature_refs: Extracted indicators applied.
            metrics: Backtest statistical metrics (Sharpe, p-value, etc.).
            rule_expression: IF/THEN evaluation logic statement.
            belief_claim: Qualitative claim to register.
            tags: Category labels.

        Returns:
            Dictionary containing compiled IDs.
        """
        # 1. Configuration & Execution Setup
        exp = self.experiment_manager.create_experiment(
            name=name,
            description=description,
            dataset_ref=dataset_ref,
            asset_universe=asset_universe,
            feature_refs=feature_refs,
            tags=tags or ["automated-scan"],
        )

        run = self.experiment_manager.start_run(
            exp.experiment_id, notes="Orchestrated automated pipeline execution"
        )

        # 2. Run Completion
        status = (
            ExperimentStatus.SUCCESS
            if metrics.get("sharpe", 0.0) > 1.0 and metrics.get("p_value", 1.0) < 0.05
            else ExperimentStatus.FAILED
        )

        conclusion = (
            f"Validation successful. Sharpe ratio: {metrics.get('sharpe', 0.0):.2f}, "
            f"p-value: {metrics.get('p_value', 1.0):.4f}."
            if status == ExperimentStatus.SUCCESS
            else "Validation failed. Hypothesis rejected due to insufficient significance."
        )

        completed_run, result = self.experiment_manager.complete_run(
            run_id=run.run_id,
            status=status,
            metrics=metrics,
            logs=[f"Calculated Sharpe: {metrics.get('sharpe')}", "Checked validation p-value"],
            conclusion=conclusion,
        )

        paper = None
        evidence_ids = []
        rule_ids = []
        belief_ids = []

        if status == ExperimentStatus.SUCCESS and result is not None:
            # 3. Paper Generation
            paper = self.paper_generator.generate_paper(exp, result)

            # 4. Knowledge Creation - Evidence Registration
            for m_name, m_val in metrics.items():
                ev = self.evidence_engine.register_evidence(
                    source_type="experiment_run",
                    source_id=completed_run.run_id,
                    description=f"Automated backtest verification metric for {exp.name}",
                    metric_name=m_name,
                    metric_value=m_val,
                    sample_size=100,  # default placeholder sample size
                )
                evidence_ids.append(ev.evidence_id)

            # 5. Knowledge Creation - Rule Registration
            rule = self.rule_engine.register_rule(
                name=f"Rule: {exp.name}",
                rule_type="research-derived",
                expression=rule_expression,
                evidence_ids=evidence_ids,
                confidence_weight=0.8,
            )
            rule_ids.append(rule.rule_id)

            # 6. Knowledge Creation - Belief Registration
            belief = self.belief_engine.create_belief(
                claim=belief_claim,
                evidence_ids=evidence_ids,
                confidence=0.85,
            )
            belief_ids.append(belief.belief_id)

        # 7. Publish ResearchCompleted event
        event_payload = {
            "experiment_id": exp.experiment_id,
            "run_id": completed_run.run_id,
            "status": status.value,
            "paper_id": paper.paper_id if paper else None,
            "evidence_ids": evidence_ids,
            "rule_ids": rule_ids,
            "belief_ids": belief_ids,
            "metrics": metrics,
        }
        event = ResearchCompleted(
            source="ResearchOrchestrator", payload=event_payload
        )
        self.event_bus.publish(event)

        return event_payload
