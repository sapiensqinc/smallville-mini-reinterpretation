"""Associative (long-term) memory.

Faithful to the paper's design — each node is an event/thought/chat with:
  - a natural language description
  - an embedding
  - a poignancy (importance) in [1, 10]
  - created + last_accessed timestamps

Retrieval scores combine recency * relevance * importance, same as the paper.

Simplifications from the original:
  - No keyword indexing; we embed everything and rely on cosine similarity.
    At demo scale (< 500 nodes) this is fine and avoids a second index to maintain.
  - No separate subject/predicate/object triple extraction. The plain description
    is sufficient for retrieval at this scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

import numpy as np


NodeType = Literal["event", "thought", "chat"]


@dataclass
class MemoryNode:
    id: int
    type: NodeType
    description: str
    poignancy: int                      # 1-10
    created_tick: int
    last_accessed_tick: int
    embedding: np.ndarray               # normalized
    evidence_ids: list[int] = field(default_factory=list)  # for thoughts

    def to_serializable(self) -> dict:
        d = asdict(self)
        d["embedding"] = self.embedding.tolist()
        return d


class AssociativeMemory:
    def __init__(self):
        self.nodes: list[MemoryNode] = []

    def __len__(self) -> int:
        return len(self.nodes)

    def add(
        self,
        *,
        type: NodeType,
        description: str,
        poignancy: int,
        embedding: np.ndarray,
        created_tick: int,
        evidence_ids: list[int] | None = None,
    ) -> MemoryNode:
        node = MemoryNode(
            id=len(self.nodes),
            type=type,
            description=description,
            poignancy=poignancy,
            created_tick=created_tick,
            last_accessed_tick=created_tick,
            embedding=embedding,
            evidence_ids=evidence_ids or [],
        )
        self.nodes.append(node)
        return node

    def score(
        self,
        *,
        query_embedding: np.ndarray,
        current_tick: int,
        recency_decay: float,
    ) -> list[tuple[MemoryNode, float]]:
        """Score all nodes with recency * relevance * importance, normalized per-axis.

        Returns list of (node, combined_score) sorted descending.
        """
        if not self.nodes:
            return []

        raw_recency = np.array(
            [recency_decay ** (current_tick - n.last_accessed_tick) for n in self.nodes],
            dtype=np.float32,
        )
        raw_relevance = np.array(
            [float(np.dot(n.embedding, query_embedding)) for n in self.nodes],
            dtype=np.float32,
        )
        raw_importance = np.array([n.poignancy / 10.0 for n in self.nodes], dtype=np.float32)

        combined = _minmax(raw_recency) + _minmax(raw_relevance) + _minmax(raw_importance)
        order = np.argsort(-combined)
        return [(self.nodes[i], float(combined[i])) for i in order]

    def top_k(
        self,
        *,
        query_embedding: np.ndarray,
        current_tick: int,
        recency_decay: float,
        k: int,
    ) -> list[MemoryNode]:
        scored = self.score(
            query_embedding=query_embedding,
            current_tick=current_tick,
            recency_decay=recency_decay,
        )
        hits = [n for n, _ in scored[:k]]
        for n in hits:
            n.last_accessed_tick = current_tick
        return hits

    def recent(self, n: int) -> list[MemoryNode]:
        return self.nodes[-n:]


def _minmax(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)
