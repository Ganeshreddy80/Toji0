"""JSON exporter formatting reports into structured JSON.
"""

from __future__ import annotations

import json


class JsonExporter:
    """Serializes report content."""

    def format_json(self, title: str, content: str) -> str:
        return json.dumps({"title": title, "content": content})
