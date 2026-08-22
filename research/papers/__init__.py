"""Research papers subpackage for generating publication-ready reports."""

from research.papers.generator import PaperGenerator
from research.papers.models import ResearchPaper

__all__ = ["ResearchPaper", "PaperGenerator"]
