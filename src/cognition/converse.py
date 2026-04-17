"""Conversation generation.

We generate a complete multi-turn dialogue in one LLM call. This is the same
shape as the paper's `agent_chat_v2`, and it avoids turn-coordination
headaches across the tick loop.

After generation, both participants add the conversation (as a single chat
node per utterance they were involved in) to their associative memory.
"""
from __future__ import annotations

from ..agent import Persona
from ..llm import Embedder, GeminiClient, ModelTier
from ..llm.prompts import (
    Conversation,
    PoignancyResponse,
    conversation_prompt,
    poignancy_prompt,
)
from .retrieve import retrieve


def generate_conversation(
    initiator: Persona,
    target: Persona,
    location_name: str,
    opening_reason: str,
    *,
    llm: GeminiClient,
    embedder: Embedder,
    current_tick: int,
    recency_decay: float,
    retrieval_k: int,
) -> list[dict]:
    """Generate a conversation, commit it to both memories, return chat events."""

    init_mem = retrieve(
        initiator,
        f"talking with {target.name}",
        embedder=embedder,
        current_tick=current_tick,
        recency_decay=recency_decay,
        k=retrieval_k,
    )
    tgt_mem = retrieve(
        target,
        f"talking with {initiator.name}",
        embedder=embedder,
        current_tick=current_tick,
        recency_decay=recency_decay,
        k=retrieval_k,
    )

    # Collect recent chat summaries between these two to avoid repetitive topics
    recent_chats = _recent_chats_between(initiator, target)

    convo = llm.generate_structured(
        tier=ModelTier.HEAVY,
        prompt=conversation_prompt(
            initiator,
            target,
            location_name=location_name,
            initiator_context=[m.description for m in init_mem],
            target_context=[m.description for m in tgt_mem],
            opening_reason=opening_reason,
            recent_chats=recent_chats,
        ),
        schema=Conversation,
        temperature=0.9,
    )

    # build event log entries
    events: list[dict] = []
    id_to_persona = {initiator.id: initiator, target.id: target}
    for turn in convo.turns:
        if turn.speaker not in id_to_persona:
            # skip malformed turns rather than fail the whole sim
            continue
        events.append(
            {
                "type": "chat",
                "actor": turn.speaker,
                "target": target.id if turn.speaker == initiator.id else initiator.id,
                "text": turn.text,
            }
        )

    # commit a single summary node to each participant's associative memory.
    # This matches the paper's approach: the chat is folded into the person's
    # life as one "I talked with X about Y" memory, not dozens of utterance nodes.
    summary = convo.summary
    for p, other in [(initiator, target), (target, initiator)]:
        description = f"{p.name} talked with {other.name} at {location_name}: {summary}"
        poignancy = llm.generate_structured(
            tier=ModelTier.FAST,
            prompt=poignancy_prompt(p.name, description),
            schema=PoignancyResponse,
            temperature=0.2,
        ).score
        emb = embedder.embed(description)
        p.a_mem.add(
            type="chat",
            description=description,
            poignancy=poignancy,
            embedding=emb,
            created_tick=current_tick,
        )
        p.scratch.importance_sum_since_last_reflect += poignancy

    # Record cooldown for both participants
    initiator.scratch.record_chat(target.id, current_tick)
    target.scratch.record_chat(initiator.id, current_tick)

    return events


def _recent_chats_between(a: Persona, b: Persona) -> list[str]:
    """Pull recent chat summaries involving the other persona from both memories."""
    results: list[str] = []
    for node in a.a_mem.recent(30):
        if node.type == "chat" and b.name in node.description:
            results.append(node.description)
    return results[-5:]  # cap at 5 most recent
