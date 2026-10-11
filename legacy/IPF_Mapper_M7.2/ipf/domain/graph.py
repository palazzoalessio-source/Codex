from __future__ import annotations
from dataclasses import dataclass
from typing import Hashable, Iterable

NodeId = Hashable

@dataclass(frozen=True)
class GraphEdge:
    source: NodeId
    target: NodeId
    semantic_id: int | None = None
    ref_id: int | None = None

@dataclass(frozen=True)
class DirectedGraph:
    nodes: frozenset[NodeId]
    edges: tuple[GraphEdge, ...]

    def outgoing(self, node: NodeId) -> tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.source == node)

    def incoming(self, node: NodeId) -> tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.target == node)

    def downstream(self, node: NodeId) -> frozenset[NodeId]:
        return frozenset(e.target for e in self.outgoing(node))

    def upstream(self, node: NodeId) -> frozenset[NodeId]:
        return frozenset(e.source for e in self.incoming(node))

    def descendants(self, node: NodeId) -> frozenset[NodeId]:
        return self._closure(node, forward=True)

    def ancestors(self, node: NodeId) -> frozenset[NodeId]:
        return self._closure(node, forward=False)

    def _closure(self, node: NodeId, forward: bool) -> frozenset[NodeId]:
        seen: set[NodeId] = set()
        todo = list(self.downstream(node) if forward else self.upstream(node))
        while todo:
            cur = todo.pop()
            if cur in seen or cur == node:
                continue
            seen.add(cur)
            nxt = self.downstream(cur) if forward else self.upstream(cur)
            todo.extend(x for x in nxt if x not in seen)
        return frozenset(seen)

    def induced(self, selected: Iterable[NodeId]) -> 'DirectedGraph':
        s = frozenset(selected)
        return DirectedGraph(s, tuple(e for e in self.edges if e.source in s and e.target in s))
