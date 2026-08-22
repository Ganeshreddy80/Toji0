"""Institutional Registry managing registration, ownership, categories, tags, and lookups.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from research_platform.strategy_lifecycle.interfaces import IStrategyRepository
from research_platform.strategy_lifecycle.models import LifecycleStage, Strategy, StrategyMetadata

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Manages strategy metadata, ownership tags, and active lookups."""

    def __init__(self, repository: IStrategyRepository) -> None:
        self._repo = repository

    def register(self, strategy_id: str, name: str, author: str) -> Strategy:
        """Register a new strategy in the system."""
        existing = self._repo.get_strategy(strategy_id)
        if existing:
            raise ValueError(f"Strategy with ID '{strategy_id}' already registered.")

        strategy = Strategy(
            strategy_id=strategy_id,
            name=name,
            author=author,
            current_stage=LifecycleStage.DRAFT,
            version_ids=[]
        )
        self._repo.save_strategy(strategy)
        logger.info("Registered strategy '%s' by author '%s'", strategy_id, author)
        return strategy

    def set_metadata(
        self,
        strategy_id: str,
        description: str,
        owner: str,
        tags: List[str] = None,
        categories: List[str] = None
    ) -> StrategyMetadata:
        """Set or update strategy metadata."""
        strategy = self._repo.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found.")

        meta = StrategyMetadata(
            strategy_id=strategy_id,
            description=description,
            owner=owner,
            tags=tags or [],
            categories=categories or []
        )
        # Store in registry
        # We can implement metadata storage inside our repo or within StrategyMetadata table.
        # Let's make sure our repository has a way to store metadata.
        # Wait, repository interface does not have save_metadata, but we can extend the repository implementation
        # to support save_metadata and get_metadata, or implement it directly.
        # Let's design the repository to handle metadata as well.
        if hasattr(self._repo, "save_metadata"):
            self._repo.save_metadata(meta)
        return meta

    def lookup(self, strategy_id: str) -> Optional[Strategy]:
        """Look up a strategy by ID."""
        return self._repo.get_strategy(strategy_id)

    def lookup_metadata(self, strategy_id: str) -> Optional[StrategyMetadata]:
        """Look up metadata for a strategy."""
        if hasattr(self._repo, "get_metadata"):
            return self._repo.get_metadata(strategy_id)
        return None

    def search(
        self,
        tag: Optional[str] = None,
        category: Optional[str] = None,
        owner: Optional[str] = None
    ) -> List[Strategy]:
        """Search strategies by tag, category, or owner."""
        results = []
        for strategy in self._repo.list_strategies():
            meta = self.lookup_metadata(strategy.strategy_id)
            if not meta:
                continue
            
            match = True
            if tag and tag not in meta.tags:
                match = False
            if category and category not in meta.categories:
                match = False
            if owner and meta.owner != owner:
                match = False
                
            if match:
                results.append(strategy)
        return results

    def archive(self, strategy_id: str) -> Strategy:
        """Move a strategy to archived stage."""
        strategy = self._repo.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found.")

        # In event driven architecture, we create a copy with stage updated to ARCHIVED
        updated = strategy.model_copy(update={"current_stage": LifecycleStage.ARCHIVED})
        self._repo.save_strategy(updated)
        logger.info("Archived strategy '%s'", strategy_id)
        return updated
