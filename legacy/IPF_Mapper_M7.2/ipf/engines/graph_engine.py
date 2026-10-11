from __future__ import annotations
from ..domain.graph import DirectedGraph, GraphEdge

class GraphEngine:
    """Builds/query graph projections. It never persists emergent structure."""

    def potential(self, snapshot, semantic_ids: set[int] | None = None) -> DirectedGraph:
        nodes = frozenset(identity.id for identity, _ in snapshot.entities)
        rels = snapshot.relations
        if semantic_ids is not None:
            rels = tuple(r for r in rels if r.semantic_id in semantic_ids)
        edges = tuple(GraphEdge(r.source_identity_id, r.target_identity_id, r.semantic_id, r.id) for r in rels)
        return DirectedGraph(nodes, edges)

    def realized(self, entity_instances, relation_instances, semantic_ids: set[int] | None = None) -> DirectedGraph:
        nodes = frozenset(i.id for i in entity_instances)
        rels = relation_instances
        if semantic_ids is not None:
            rels = tuple(r for r in rels if r.semantic_id in semantic_ids)
        edges = tuple(GraphEdge(r.source_instance_id, r.target_instance_id, r.semantic_id, r.id) for r in rels)
        return DirectedGraph(nodes, edges)

    def active(self, potential: DirectedGraph, active_nodes) -> DirectedGraph:
        """Projection only. Determining active_nodes is intentionally delegated to an activation resolver."""
        return potential.induced(active_nodes)
