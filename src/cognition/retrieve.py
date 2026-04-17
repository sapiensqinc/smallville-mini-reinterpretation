"""Retrieval: pick top-k relevant memories for a natural-language query."""
from __future__ import annotations

from ..agent import Persona
from ..llm import Embedder
from ..memory import MemoryNode


def retrieve(
    persona: Persona,
    query: str,
    *,
    embedder: Embedder,
    current_tick: int,
    recency_decay: float,
    k: int,
) -> list[MemoryNode]:
    if len(persona.a_mem) == 0:
        return []
    q_emb = embedder.embed(query)
    return persona.a_mem.top_k(
        query_embedding=q_emb,
        current_tick=current_tick,
        recency_decay=recency_decay,
        k=k,
    )
