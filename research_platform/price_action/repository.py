"""Thread-safe persistence repository for price action structures."""

from __future__ import annotations

import logging
import threading
from typing import Dict, Any, List, Optional
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.price_action.models import (
    SwingPoint, MarketStructureChange, LiquiditySweep, BlockStructure, ImbalanceGap, SessionPeriod
)

logger = logging.getLogger(__name__)


class PriceActionRepository:
    """Coordinates persistence updates of active price action structures."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._swings: Dict[str, List[Dict[str, Any]]] = {}
        self._structure_changes: Dict[str, List[Dict[str, Any]]] = {}
        self._blocks: Dict[str, List[Dict[str, Any]]] = {}
        self._gaps: Dict[str, List[Dict[str, Any]]] = {}
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}

    def _get_pg_repo(self) -> Optional[Any]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
            session_manager = DatabaseSessionManager(db)
            return PostgresConfigurationRepository(session_manager)
        return None

    def save_swing(self, symbol: str, swing: SwingPoint) -> None:
        swing_data = swing.model_dump(mode="json")
        with self._lock:
            lst = self._swings.setdefault(symbol, [])
            lst.append(swing_data)
            if len(lst) > 1000:
                lst.pop(0)

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter(f"pa_swings_{symbol}", self._swings[symbol])
            except Exception as e:
                logger.error("Failed to save swing point to PostgreSQL: %s", e)

    def get_swings(self, symbol: str) -> List[SwingPoint]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter(f"pa_swings_{symbol}")
                if val:
                    return [SwingPoint.model_validate(x) for x in val]
            except Exception as e:
                logger.error("Failed to load swings from PostgreSQL: %s", e)

        with self._lock:
            return [SwingPoint.model_validate(x) for x in self._swings.get(symbol, [])]

    def save_structure_change(self, symbol: str, change: MarketStructureChange) -> None:
        change_data = change.model_dump(mode="json")
        with self._lock:
            lst = self._structure_changes.setdefault(symbol, [])
            lst.append(change_data)
            if len(lst) > 1000:
                lst.pop(0)

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter(f"pa_structure_{symbol}", self._structure_changes[symbol])
            except Exception as e:
                logger.error("Failed to save structure shift to PostgreSQL: %s", e)

    def get_structure_changes(self, symbol: str) -> List[MarketStructureChange]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter(f"pa_structure_{symbol}")
                if val:
                    return [MarketStructureChange.model_validate(x) for x in val]
            except Exception as e:
                logger.error("Failed to load structures from PostgreSQL: %s", e)

        with self._lock:
            return [MarketStructureChange.model_validate(x) for x in self._structure_changes.get(symbol, [])]

    def save_block(self, symbol: str, block: BlockStructure) -> None:
        block_data = block.model_dump(mode="json")
        with self._lock:
            lst = self._blocks.setdefault(symbol, [])
            lst.append(block_data)
            if len(lst) > 1000:
                lst.pop(0)

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter(f"pa_blocks_{symbol}", self._blocks[symbol])
            except Exception as e:
                logger.error("Failed to save block structure to PostgreSQL: %s", e)

    def get_blocks(self, symbol: str) -> List[BlockStructure]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter(f"pa_blocks_{symbol}")
                if val:
                    return [BlockStructure.model_validate(x) for x in val]
            except Exception as e:
                logger.error("Failed to load blocks from PostgreSQL: %s", e)

        with self._lock:
            return [BlockStructure.model_validate(x) for x in self._blocks.get(symbol, [])]

    def save_gap(self, symbol: str, gap: ImbalanceGap) -> None:
        gap_data = gap.model_dump(mode="json")
        with self._lock:
            lst = self._gaps.setdefault(symbol, [])
            lst.append(gap_data)
            if len(lst) > 1000:
                lst.pop(0)

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter(f"pa_gaps_{symbol}", self._gaps[symbol])
            except Exception as e:
                logger.error("Failed to save gap to PostgreSQL: %s", e)

    def get_gaps(self, symbol: str) -> List[ImbalanceGap]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter(f"pa_gaps_{symbol}")
                if val:
                    return [ImbalanceGap.model_validate(x) for x in val]
            except Exception as e:
                logger.error("Failed to load gaps from PostgreSQL: %s", e)

        with self._lock:
            return [ImbalanceGap.model_validate(x) for x in self._gaps.get(symbol, [])]

    def clear(self) -> None:
        with self._lock:
            self._swings.clear()
            self._structure_changes.clear()
            self._blocks.clear()
            self._gaps.clear()
            self._sessions.clear()
