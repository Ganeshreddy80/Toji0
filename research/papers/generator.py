"""Generator service to automatically compile experiments into ResearchPaper objects."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research.experiments.models import ExperimentResult, ResearchExperiment
from research.papers.models import ResearchPaper


class PaperGenerator:
    """Compiles ResearchExperiment details and ExperimentResults into a publication schema."""

    @staticmethod
    def generate_paper(
        experiment: ResearchExperiment,
        result: ExperimentResult,
        title: str | None = None,
        abstract: str | None = None,
        weaknesses: list[str] | None = None,
        future_work: list[str] | None = None,
    ) -> ResearchPaper:
        """Compile a quantitative paper from an experiment and its results."""
        paper_id = str(uuid.uuid4())
        default_title = f"Quantitative Analysis Report: {experiment.name} (v{experiment.version})"

        # Generate a default abstract if not provided
        default_abstract = (
            f"This paper analyzes the performance of the {experiment.name} quant model. "
            f"The experiment targeted the asset universe: {', '.join(experiment.asset_universe)}. "
            f"Under testing, the model achieved metrics including: "
            f"{', '.join(f'{k}={v:.4f}' for k, v in result.metrics.items())}."
        )

        # Standard quantitative methodology placeholder description
        methodology_desc = (
            f"The research followed a structured pipeline of data loading on dataset "
            f"'{experiment.dataset_ref}' followed by feature extraction for columns "
            f"[{', '.join(experiment.feature_refs)}]. Performance and risk metrics "
            f"were evaluated over the target regimes."
        )

        lessons = [
            f"Hypothesis validation concluded with results: {result.conclusion}",
            f"Successfully processed {len(experiment.feature_refs)} features on {len(experiment.asset_universe)} assets.",
        ]

        return ResearchPaper(
            paper_id=paper_id,
            experiment_id=experiment.experiment_id,
            title=title or default_title,
            abstract=abstract or default_abstract,
            hypothesis=experiment.description,
            methodology=methodology_desc,
            dataset=experiment.dataset_ref,
            features=experiment.feature_refs,
            statistics={k: v for k, v in result.metrics.items() if "stat" in k.lower() or "p_val" in k.lower()},
            results={k: v for k, v in result.metrics.items() if "stat" not in k.lower() and "p_val" not in k.lower()},
            weaknesses=weaknesses or ["Potential overfitting on history.", "Regime shift sensitivity."],
            future_work=future_work or ["Add out-of-sample forward testing.", "Integrate alternative news sentiment."],
            lessons_learned=lessons,
            published_at=datetime.now(timezone.utc),
        )
