"""Planning — daily plan (once per simulated day) + per-tick action decision."""
from __future__ import annotations

from datetime import datetime

from ..agent import Persona
from ..llm import GeminiClient, ModelTier
from ..llm.prompts import (
    ActionDecision,
    DailyPlan,
    action_prompt,
    daily_plan_prompt,
    persona_identity,
)
from ..memory import MemoryNode
from ..world import World
from .perceive import Perception


def ensure_daily_plan(
    persona: Persona, current_time: datetime, llm: GeminiClient
) -> None:
    today = current_time.strftime("%Y-%m-%d")
    if persona.scratch.plan_generated_for_day == today and persona.scratch.daily_plan:
        return
    resp = llm.generate_structured(
        tier=ModelTier.PLAN,
        prompt=daily_plan_prompt(persona, today),
        schema=DailyPlan,
        system=persona_identity(persona),
        temperature=0.8,
    )
    persona.scratch.daily_plan = resp.plan
    persona.scratch.plan_generated_for_day = today


def decide_action(
    persona: Persona,
    perception: Perception,
    memories: list[MemoryNode],
    world: World,
    current_time: datetime,
    llm: GeminiClient,
    current_tick: int = 0,
) -> ActionDecision:
    ensure_daily_plan(persona, current_time, llm)

    prompt = action_prompt(
        persona,
        current_time=current_time.strftime("%a %Y-%m-%d %H:%M"),
        current_location_name=perception.here.name,
        adjacent_locations=[(loc.id, loc.name) for loc in perception.adjacent],
        others_here=[(p.id, p.name) for p in perception.others_here],
        others_elsewhere=[
            (p.id, p.name, loc.name) for p, loc in perception.others_elsewhere
        ],
        daily_plan=persona.scratch.daily_plan,
        recent_memory=[m.description for m in memories],
    )
    decision = llm.generate_structured(
        tier=ModelTier.PLAN,
        prompt=prompt,
        schema=ActionDecision,
        system=persona_identity(persona),
        temperature=0.8,
    )

    # Validate: if the model picks move to a non-adjacent location, or speak to
    # someone not here, fall back to idle. Cheaper than re-prompting.
    if decision.action == "move":
        if not decision.target_location or not world.can_move(
            perception.here.id, decision.target_location
        ):
            decision.action = "idle"
            decision.target_location = None
            if not decision.activity:
                decision.activity = "pausing to think"
    elif decision.action == "speak":
        here_ids = {p.id for p in perception.others_here}
        if not decision.target_person or decision.target_person not in here_ids:
            decision.action = "idle"
            decision.target_person = None
            if not decision.activity:
                decision.activity = "pausing to think"
        elif not persona.scratch.can_chat_with(decision.target_person, current_tick):
            decision.action = "idle"
            decision.activity = decision.activity or "quietly working nearby"
            decision.target_person = None

    return decision
