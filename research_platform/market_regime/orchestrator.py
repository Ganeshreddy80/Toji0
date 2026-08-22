"""Market Regime Intelligence Orchestrator coordinating detectors, transitions, and external subsystem wiring.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.market_regime.interfaces import IMarketRegimeOrchestrator
from research_platform.market_regime.models import (
    HistoricalRegimeRecord,
    MarketRegime,
    MarketStructure,
    RegimeTransition,
)
from research_platform.market_regime.repository import MarketRegimeRepository
from research_platform.market_regime.detection import RegimeDetectionEngine
from research_platform.market_regime.transition import RegimeTransitionEngine
from research_platform.market_regime.structure import MarketStructureAnalyzer
from research_platform.market_regime.events import (
    LiquidityRegimeChanged,
    MarketStructureAnalyzed,
    RegimeDetected,
    RegimeTransitioned,
    TrendRegimeChanged,
    VolatilityRegimeChanged,
)

logger = logging.getLogger(__name__)


class MarketRegimeOrchestrator(IMarketRegimeOrchestrator):
    """Central orchestrator managing regime assessments and publishing semantic graph bindings."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = MarketRegimeRepository()

        # Engines
        self._detection_engine = RegimeDetectionEngine()
        self._transition_engine = RegimeTransitionEngine()
        self._structure_analyzer = MarketStructureAnalyzer()

    @property
    def repository(self) -> MarketRegimeRepository:
        return self._repo

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, record: MarketRegime) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            # We can publish as a generic record or dict to category 'market_regimes'
            mem_orch.publish_memory("market_regimes", record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, record: MarketRegime, structure: Optional[MarketStructure] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Asset node
            kg_orch.register_node(
                node_id=record.symbol,
                node_type="ASSET",
                subsystem="market_regime",
                event="RegimeDetected",
                author="system",
                properties={"symbol": record.symbol}
            )

            # Register Regime node
            regime_node_id = f"regime-{record.symbol}-{record.timestamp.isoformat()}"
            kg_orch.register_node(
                node_id=regime_node_id,
                node_type="MARKET_REGIME",
                subsystem="market_regime",
                event="RegimeDetected",
                author="system",
                properties={
                    "trend": record.regime_type.value,
                    "volatility": record.volatility.value,
                    "liquidity": record.liquidity.value,
                    "confidence": record.confidence_score
                }
            )

            # Link Asset to Regime
            kg_orch.link_nodes(
                source_id=record.symbol,
                target_id=regime_node_id,
                relationship_type="uses",
                subsystem="market_regime"
            )

            # Link structure data if available
            if structure:
                struct_node_id = f"struct-{record.symbol}-{structure.timestamp.isoformat()}"
                kg_orch.register_node(
                    node_id=struct_node_id,
                    node_type="MARKET_STRUCTURE",
                    subsystem="market_regime",
                    event="MarketStructureAnalyzed",
                    author="system",
                    properties={
                        "support": structure.support_levels,
                        "resistance": structure.resistance_levels
                    }
                )
                kg_orch.link_nodes(
                    source_id=record.symbol,
                    target_id=struct_node_id,
                    relationship_type="references",
                    subsystem="market_regime"
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def analyze_regime(
        self,
        symbol: str,
        prices: List[float],
        volumes: List[float],
        spreads: List[float],
        atr_values: List[float],
        highs: List[float] = None,
        lows: List[float] = None
    ) -> MarketRegime:
        """Run complete regime analysis, track transitions, update memory and knowledge graph."""
        old_regime = self._repo.get_latest_regime(symbol)

        # 1. Detect regime
        new_regime = self._detection_engine.detect_global_regime(symbol, prices, volumes, spreads, atr_values)

        # 2. Save regime record
        record = HistoricalRegimeRecord(
            record_id=f"rec-{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            regime=new_regime,
            timestamp=new_regime.timestamp
        )
        self._repo.save_regime(record)

        # 3. Publish RegimeDetected event
        self._event_bus.publish(RegimeDetected(payload={
            "symbol": symbol,
            "regime": new_regime.regime_type.value,
            "volatility": new_regime.volatility.value,
            "liquidity": new_regime.liquidity.value
        }))

        # 4. Check for transition
        transition = self._transition_engine.check_transition(old_regime, new_regime)
        if transition:
            self._repo.save_transition(transition)
            self._event_bus.publish(RegimeTransitioned(payload={
                "symbol": symbol,
                "old_regime": old_regime.regime_type.value if old_regime else "NONE",
                "new_regime": new_regime.regime_type.value
            }))

            # Publish specific change events
            if not old_regime or old_regime.regime_type != new_regime.regime_type:
                self._event_bus.publish(TrendRegimeChanged(payload={"symbol": symbol, "trend": new_regime.regime_type.value}))
            if not old_regime or old_regime.volatility != new_regime.volatility:
                self._event_bus.publish(VolatilityRegimeChanged(payload={"symbol": symbol, "volatility": new_regime.volatility.value}))
            if not old_regime or old_regime.liquidity != new_regime.liquidity:
                self._event_bus.publish(LiquidityRegimeChanged(payload={"symbol": symbol, "liquidity": new_regime.liquidity.value}))

        # 5. Run structure analysis
        structure = self._structure_analyzer.analyze_structure(
            prices=prices,
            highs=highs or prices,
            lows=lows or prices
        )
        # Update structure symbol
        structure = structure.model_copy(update={"symbol": symbol})
        self._repo.save_market_structure(structure)
        self._event_bus.publish(MarketStructureAnalyzed(payload={
            "symbol": symbol,
            "breakouts": structure.breakouts
        }))

        # 6. Integrate Memory & Graph
        self._publish_memory_record(new_regime)
        self._update_knowledge_graph(new_regime, structure)

        return new_regime
