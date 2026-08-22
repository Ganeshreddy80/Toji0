"""Bootstrap resampling engine for Monte Carlo simulations (Sprint 8C)."""

from __future__ import annotations

import abc
import math
from typing import Optional

import numpy as np


class IBootstrapStrategy(abc.ABC):
    """Abstract interface for bootstrap resampling strategies."""

    @abc.abstractmethod
    def resample(
        self,
        data: np.ndarray,
        num_paths: int,
        path_length: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> np.ndarray:
        """Resample input sequence into (num_paths, path_length) array.

        Args:
            data: 1D numpy array of returns or trade PnL ratios.
            num_paths: Number of simulation paths to generate.
            path_length: Desired length of each path. Defaults to len(data).
            rng: NumPy random Generator instance for strict determinism.

        Returns:
            2D numpy array of shape (num_paths, target_path_length).
        """


class TradeBootstrap(IBootstrapStrategy):
    """Trade-level resampling.

    Supports random resampling with replacement (default) and sequential trade order
    preservation with random starting offset rotation when preserve_trade_order=True.
    """

    def __init__(self, preserve_trade_order: bool = False) -> None:
        self.preserve_trade_order = preserve_trade_order

    def resample(
        self,
        data: np.ndarray,
        num_paths: int,
        path_length: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> np.ndarray:
        if rng is None:
            rng = np.random.default_rng(42)

        data = np.asarray(data, dtype=np.float64).ravel()
        n_elements = len(data)

        if n_elements == 0:
            target_len = path_length if path_length is not None else 0
            return np.zeros((num_paths, target_len), dtype=np.float64)

        target_len = path_length if path_length is not None else n_elements
        if target_len == 0:
            return np.zeros((num_paths, 0), dtype=np.float64)

        if self.preserve_trade_order:
            # Preserve original sequential trade order via circular shift offset per path
            start_indices = rng.choice(n_elements, size=num_paths, replace=True)
            seq_offsets = np.arange(target_len)[np.newaxis, :]  # Shape: (1, target_len)
            indices = (start_indices[:, np.newaxis] + seq_offsets) % n_elements  # Shape: (num_paths, target_len)
            return data[indices]

        # Standard random sampling with replacement
        indices = rng.choice(n_elements, size=(num_paths, target_len), replace=True)
        return data[indices]


class ReturnBootstrap(IBootstrapStrategy):
    """Periodic return-level random resampling with replacement."""

    def resample(
        self,
        data: np.ndarray,
        num_paths: int,
        path_length: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> np.ndarray:
        if rng is None:
            rng = np.random.default_rng(42)

        data = np.asarray(data, dtype=np.float64).ravel()
        n_elements = len(data)

        if n_elements == 0:
            target_len = path_length if path_length is not None else 0
            return np.zeros((num_paths, target_len), dtype=np.float64)

        target_len = path_length if path_length is not None else n_elements
        if target_len == 0:
            return np.zeros((num_paths, 0), dtype=np.float64)

        indices = rng.choice(n_elements, size=(num_paths, target_len), replace=True)
        return data[indices]


class BlockBootstrap(IBootstrapStrategy):
    """Overlapping block bootstrap resampling to preserve temporal correlation structures.

    Fully vectorized O(1) NumPy implementation without Python loops across paths.
    """

    def __init__(self, block_size: int = 5) -> None:
        if block_size < 1:
            raise ValueError(f"block_size must be >= 1, got {block_size}")
        self.block_size = block_size

    def resample(
        self,
        data: np.ndarray,
        num_paths: int,
        path_length: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> np.ndarray:
        if rng is None:
            rng = np.random.default_rng(42)

        data = np.asarray(data, dtype=np.float64).ravel()
        n_elements = len(data)

        if n_elements == 0:
            target_len = path_length if path_length is not None else 0
            return np.zeros((num_paths, target_len), dtype=np.float64)

        target_len = path_length if path_length is not None else n_elements
        if target_len == 0:
            return np.zeros((num_paths, 0), dtype=np.float64)

        actual_block_size = min(self.block_size, n_elements)
        n_blocks_possible = n_elements - actual_block_size + 1

        # Calculate number of blocks needed to cover target_len
        num_blocks_needed = math.ceil(target_len / actual_block_size)

        # Draw random block start indices for each path: shape (num_paths, num_blocks_needed)
        start_indices = rng.choice(n_blocks_possible, size=(num_paths, num_blocks_needed), replace=True)

        # Fully vectorized block index construction using NumPy broadcasting
        offsets = np.arange(actual_block_size, dtype=np.int64)[np.newaxis, np.newaxis, :]
        block_indices = (start_indices[:, :, np.newaxis] + offsets).reshape(num_paths, -1)

        resampled_paths = data[block_indices]
        return resampled_paths[:, :target_len]
