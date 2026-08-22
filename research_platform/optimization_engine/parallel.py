"""Parallel execution task executor wrapper.
"""

from __future__ import annotations

import concurrent.futures
from typing import Callable, List, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class ParallelTaskExecutor:
    """Dispatches trial runs in parallel using worker threads/processes."""

    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers

    def map_tasks(self, fn: Callable[[T], R], tasks: List[T]) -> List[R]:
        """Map function over tasks in parallel worker pool."""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Execute tasks
            future_to_task = {executor.submit(fn, task): task for task in tasks}
            
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    # Ignore or pass exceptions upward as needed
                    pass
        return results
