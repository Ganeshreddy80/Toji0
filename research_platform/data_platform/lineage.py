"""Lineage Engine tracking data and pipeline dependency chains.
"""

from __future__ import annotations

import threading
from typing import Dict, List

from research_platform.data_platform.interfaces import ILineageEngine
from research_platform.data_platform.models import LineageRecord


class LineageEngine(ILineageEngine):
    """Tracks dataset, feature, and strategy execution dependency DAGs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, LineageRecord] = {}

    def register_lineage(self, record: LineageRecord) -> None:
        with self._lock:
            self._records[record.target_id] = record

    def get_upstream(self, target_id: str) -> List[str]:
        """Recursively traverse upstream dependencies to identify root sources."""
        visited = set()
        upstream = []
        
        def traverse(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            
            with self._lock:
                record = self._records.get(node_id)
                
            if record:
                for src in record.source_ids:
                    if src not in upstream:
                        upstream.append(src)
                    traverse(src)

        traverse(target_id)
        return upstream
