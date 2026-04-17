"""Reflection — periodic consolidation of recent experiences into insights.

Trigger: when sum of recent event poignancies crosses a threshold
(same mechanism as the paper, just with our own threshold).

Process:
  1. Ask the persona "what 3 questions are you implicitly asking?" (focal points).
  2. For each question, retrieve relevant recent memories, then ask for 3-5
     insights grounded in that evidence.
  3. Each insight becomes a "thought" node in associative memory, linked back
     to the evidence nodes it was derived from.
"""
from __future__ import annotations

from ..agent import Persona
from ..llm import Embedder, GeminiClient, ModelTier
from ..llm.prompts import (
    FocalPoints,
    Insights,
    PoignancyResponse,
    focal_points_prompt,
    insights_prompt,
    persona_identity,
    poignancy_prompt,
)
from .retrieve import retrieve


def should_reflect(persona: Persona, threshold: float) -> bool:
    return persona.scratch.importance_sum_since_last_reflect >= threshold


def reflect(
    persona: Persona,
    *,
    llm: GeminiClient,
    embedder: Embedder,
    current_tick: int,
    recency_decay: float,
    retrieval_k: int,
    focal_point_count: int = 3,
) -> list[str]:
    # 1. recent memories seed the focal-point question generation
    recent = persona.a_mem.recent(30)
    focals = llm.generate_structured(
        tier=ModelTier.HEAVY,
        prompt=focal_points_prompt(persona, [m.description for m in recent]),
        schema=FocalPoints,
        system=persona_identity(persona),
        temperature=0.7,
    ).questions[:focal_point_count]

    all_new_insights: list[str] = []

    for question in focals:
        evidence_nodes = retrieve(
            persona,
            question,
            embedder=embedder,
            current_tick=current_tick,
            recency_decay=recency_decay,
            k=retrieval_k,
        )
        if not evidence_nodes:
            continue
        insights = llm.generate_structured(
            tier=ModelTier.HEAVY,
            prompt=insights_prompt(
                persona,
                question,
                [m.description for m in evidence_nodes],
            ),
            schema=Insights,
            system=persona_identity(persona),
            temperature=0.7,
        ).insights

        for ins in insights:
            poignancy = llm.generate_structured(
                tier=ModelTier.FAST,
                prompt=poignancy_prompt(persona.name, ins),
                schema=PoignancyResponse,
                temperature=0.2,
            ).score
            emb = embedder.embed(ins)
            persona.a_mem.add(
                type="thought",
                description=ins,
                poignancy=poignancy,
                embedding=emb,
                created_tick=current_tick,
                evidence_ids=[n.id for n in evidence_nodes],
            )
            all_new_insights.append(ins)

    persona.scratch.importance_sum_since_last_reflect = 0.0
    return all_new_insights
