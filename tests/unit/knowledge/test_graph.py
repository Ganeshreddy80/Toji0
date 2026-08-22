"""Unit tests for the KnowledgeGraph ontology node and relationship traversals."""

from __future__ import annotations

import pytest

from knowledge.graph.manager import KnowledgeGraph
from knowledge.models import Relationship


def test_add_nodes_and_edges():
    """Verify adding nodes and relational edges to the graph."""
    graph = KnowledgeGraph()
    
    graph.add_node("asset-BTC", "Asset", {"symbol": "BTC/USDT"})
    graph.add_node("strat-momentum", "Strategy", {"name": "EMA Momentum"})
    
    # Verify nodes listed by type
    assets = graph.list_nodes_by_type("Asset")
    assert assets == ["asset-BTC"]
    
    # Add relationship BTC -> strat-momentum
    edge = graph.add_edge("asset-BTC", "strat-momentum", "applies_to")
    assert isinstance(edge, Relationship)
    assert edge.source_id == "asset-BTC"
    assert edge.target_id == "strat-momentum"
    assert edge.rel_type == "applies_to"
    
    # Attempting to link non-existent nodes should raise KeyError
    with pytest.raises(KeyError):
        graph.add_edge("asset-BTC", "nonexistent-node", "rel")


def test_get_neighbors():
    """Verify retrieving neighboring nodes and filtering by relation types."""
    graph = KnowledgeGraph()
    graph.add_node("N1", "Type1")
    graph.add_node("N2", "Type1")
    graph.add_node("N3", "Type1")
    
    graph.add_edge("N1", "N2", "supports")
    graph.add_edge("N1", "N3", "contradicts")
    
    neighbors_all = graph.get_neighbors("N1")
    assert len(neighbors_all) == 2
    
    neighbors_supports = graph.get_neighbors("N1", rel_type="supports")
    assert neighbors_supports == [("N2", "supports")]


def test_find_shortest_path_bfs():
    """Verify BFS shortest path routing algorithm works for multiple hops."""
    graph = KnowledgeGraph()
    # Path: A -> B -> C -> D
    # Distant: E (disconnected)
    for n in ["A", "B", "C", "D", "E"]:
        graph.add_node(n, "Node")
        
    graph.add_edge("A", "B", "link")
    graph.add_edge("B", "C", "link")
    graph.add_edge("C", "D", "link")
    
    # Direct search path
    path = graph.find_path("A", "D")
    assert path == ["A", "B", "C", "D"]
    
    # Disconnected path should return None
    assert graph.find_path("A", "E") is None
    
    # Start equals End
    assert graph.find_path("A", "A") == ["A"]
