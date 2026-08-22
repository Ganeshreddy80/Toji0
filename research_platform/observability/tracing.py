"""Tracing Engine tracking execution timing spans.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from research_platform.observability.interfaces import ITracingEngine
from research_platform.observability.models import Span


class TracingEngine(ITracingEngine):
    """Generates execution spans, automatically calculating timing durations."""

    def __init__(self) -> None:
        self._active_spans: Dict[str, Span] = {}

    def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Span:
        """Construct and register execution span start."""
        span_id = str(uuid.uuid4())
        tr_id = trace_id or str(uuid.uuid4())
        
        span = Span(
            span_id=span_id,
            trace_id=tr_id,
            name=name,
            start_time=datetime.now(timezone.utc),
            parent_span_id=parent_id
        )
        self._active_spans[span_id] = span
        return span

    def stop_span(self, span_id: str) -> Span:
        """Conclude span execution, calculating millisecond duration."""
        span = self._active_spans.pop(span_id, None)
        if not span:
            raise KeyError(f"No active span found with ID: {span_id}")

        end_time = datetime.now(timezone.utc)
        diff = end_time - span.start_time
        dur_ms = diff.total_seconds() * 1000.0

        updated_span = Span(
            span_id=span.span_id,
            trace_id=span.trace_id,
            name=span.name,
            start_time=span.start_time,
            end_time=end_time,
            duration_ms=dur_ms,
            parent_span_id=span.parent_span_id
        )
        return updated_span
