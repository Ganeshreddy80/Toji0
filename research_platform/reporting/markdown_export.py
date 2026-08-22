"""Markdown exporter formatting reports into markdown strings.
"""

from __future__ import annotations


class MarkdownExporter:
    """Formats report into markdown syntax."""

    def format_markdown(self, title: str, content: str) -> str:
        return f"# {title}\n\n{content}"
