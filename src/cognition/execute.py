"""Execute: apply a decided action to persona state + record events.

This is where we also score + embed the resulting event and add it to
associative memory. That way, the next tick's perception/plan will see
what just happened.
"""
from __future__ import annotations

from ..agent import Persona
from ..llm import Embedder, GeminiClient, ModelTier
from ..llm.prompts import PoignancyResponse, poignancy_prompt
from ..llm.prompts import ActionDecision
from ..world import World


def execute(
    persona: Persona,
    decision: ActionDecision,
    world: World,
    *,
    llm: GeminiClient,
    embedder: Embedder,
    current_tick: int,
) -> dict:
    """Apply the decision. Returns an event dict for the recorder."""
    event: dict
    if decision.action == "move":
        src = persona.scratch.current_location
        dst = decision.target_location  # already validated by decide_action
        persona.scratch.current_location = dst
        persona.scratch.current_activity = decision.activity
        description = (
            f"{persona.name} walked from {world.location(src).name} to "
            f"{world.location(dst).name} ({decision.activity})"
        )
        event = {
            "type": "move",
            "actor": persona.id,
            "from": src,
            "to": dst,
            "text": decision.activity,
        }
    elif decision.action == "speak":
        # execution of the *conversation* happens in converse.generate_conversation;
        # here we just mark intent. The engine will pick it up.
        persona.scratch.current_activity = decision.activity
        description = f"{persona.name} approached {decision.target_person} to talk ({decision.activity})"
        event = {
            "type": "speak_intent",
            "actor": persona.id,
            "target": decision.target_person,
            "text": decision.activity,
        }
    else:  # idle
        persona.scratch.current_activity = decision.activity
        description = f"{persona.name}: {decision.activity}"
        event = {
            "type": "action",
            "actor": persona.id,
            "text": decision.activity,
        }

    _record_event_memory(
        persona,
        description=description,
        llm=llm,
        embedder=embedder,
        current_tick=current_tick,
    )
    return event


def _record_event_memory(
    persona: Persona,
    *,
    description: str,
    llm: GeminiClient,
    embedder: Embedder,
    current_tick: int,
) -> None:
    poignancy = llm.generate_structured(
        tier=ModelTier.FAST,
        prompt=poignancy_prompt(persona.name, description),
        schema=PoignancyResponse,
        temperature=0.2,
    ).score
    emb = embedder.embed(description)
    persona.a_mem.add(
        type="event",
        description=description,
        poignancy=poignancy,
        embedding=emb,
        created_tick=current_tick,
    )
    persona.scratch.importance_sum_since_last_reflect += poignancy
