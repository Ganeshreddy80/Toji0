"""Cross-Validation splitters (Blocked CV, Purged CV, Embargo CV, and CPCV).
"""

from __future__ import annotations

import pandas as pd
from typing import List, Tuple


class TimeSeriesCVSplitter:
    """Implements quantitative cross-validation partitioning with purging and embargoing."""

    @staticmethod
    def blocked_split(total_len: int, num_splits: int = 5) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Generate contiguous blocked train/test index splits without shuffling.

        Returns:
            List of ((train_start, train_end), (test_start, test_end)) indices.
        """
        splits = []
        block_size = total_len // num_splits
        for i in range(num_splits):
            test_start = i * block_size
            test_end = (i + 1) * block_size if i < num_splits - 1 else total_len
            
            # Train on the rest
            train_ranges = []
            if test_start > 0:
                train_ranges.append((0, test_start))
            if test_end < total_len:
                train_ranges.append((test_end, total_len))
            
            # Combine train index spans (for simplicity, pick largest contiguous chunk or split ranges)
            splits.append((train_ranges[0] if train_ranges else (0, 0), (test_start, test_end)))
        return splits

    @staticmethod
    def purge_and_embargo(
        train_ranges: List[Tuple[int, int]],
        test_range: Tuple[int, int],
        purge_window: int = 10,
        embargo_window: int = 20
    ) -> List[Tuple[int, int]]:
        """Purge and embargo training ranges overlapping with test range windows.

        Args:
            train_ranges: List of (start, end) index spans for training.
            test_range: (start, end) index span for testing.
            purge_window: index window to remove before the test start (to prevent overlapping features).
            embargo_window: index window to remove after the test end (to prevent autocorrelation leak).

        Returns:
            Pruned list of training (start, end) index spans.
        """
        test_start, test_end = test_range
        purged_ranges = []

        for start, end in train_ranges:
            if start < test_start and end > test_start:
                # Truncate end of block to start of test minus purge window
                end = max(test_start - purge_window, start)
            
            if start < test_end and end > test_end:
                # Shift start of block to end of test plus embargo window
                start = min(test_end + embargo_window, end)

            # Check if block is still valid/positive size
            if start < end:
                purged_ranges.append((start, end))

        return purged_ranges

    @classmethod
    def cpcv_split(
        cls,
        total_len: int,
        num_partitions: int = 6,
        num_test_partitions: int = 2,
        purge_window: int = 10,
        embargo_window: int = 20
    ) -> List[Tuple[List[Tuple[int, int]], Tuple[int, int]]]:
        """Combinatorial Purged Cross-Validation (CPCV).

        Splits data into N partitions, creates combinations of training and testing blocks,
        and applies purging and embargoing.

        Returns:
            List of (purged_train_ranges, test_range_span).
        """
        import itertools
        partition_size = total_len // num_partitions
        partitions = [(i * partition_size, (i + 1) * partition_size) for i in range(num_partitions)]
        
        splits = []
        indices = list(range(num_partitions))
        
        # Combinations of test partitions
        for test_indices in itertools.combinations(indices, num_test_partitions):
            # Pick contiguous test range or list of test partitions
            # For simplicity in evaluation, we take the span of the test partitions
            test_starts = [partitions[idx][0] for idx in test_indices]
            test_ends = [partitions[idx][1] for idx in test_indices]
            test_range = (min(test_starts), max(test_ends))
            
            # Train indices are the remaining
            train_indices = [idx for idx in indices if idx not in test_indices]
            train_ranges = [partitions[idx] for idx in train_indices]
            
            # Apply purge and embargo
            purged_train = cls.purge_and_embargo(
                train_ranges,
                test_range,
                purge_window,
                embargo_window
            )
            splits.append((purged_train, test_range))
        return splits
