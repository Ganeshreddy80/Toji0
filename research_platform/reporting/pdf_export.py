"""PDF exporter formatting reports into PDF layouts.
"""

from __future__ import annotations


class PdfExporter:
    """Simulates PDF packaging."""

    def format_pdf(self, title: str, content: str) -> str:
        return f"%PDF-1.4\n% TITLE: {title}\n% CONTENT: {content}"
