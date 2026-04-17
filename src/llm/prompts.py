"""Prompt builders + Pydantic response schemas for every LLM call.

Every function here returns either (prompt_str, ResponseSchema) or plain
prompt text. The caller in cognition/* picks the model tier and calls
GeminiClient.generate_structured.

Keeping prompts + schemas co-located (rather than in ~50 .txt template files
like the original) makes it much easier to iterate: the prompt, its variables,
and its expected output live in one place.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- shared persona identity block ----------

def persona_identity(p) -> str:
    """Render the persona's stable identity. Used as system instruction."""
    return (
        f"You are simulating {p.name}, age {p.age}.\n"
        f"Innate traits: {p.innate}\n"
        f"Background: {p.learned}\n"
        f"Currently: {p.currently}\n"
        f"Lifestyle: {p.lifestyle}\n"
        f"You act in character at all times. Keep outputs concise."
    )


# ---------- Importance / poignancy ----------

class PoignancyResponse(BaseModel):
    score: int = Field(ge=1, le=10, description="1=mundane, 10=life-changing")


def poignancy_prompt(persona_name: str, event_description: str) -> str:
    return (
        f"On a scale of 1 (mundane, e.g. brushing teeth) to 10 "
        f"(extremely poignant, e.g. a breakup or the death of a loved one), "
        f"rate how poignant this event is for {persona_name}.\n\n"
        f"Event: {event_description}\n\n"
        f"Return only a JSON object with a single field 'score'."
    )


# ---------- Daily plan ----------

class DailyPlan(BaseModel):
    plan: list[str] = Field(description="5-8 broad activities for the day, in order")


def daily_plan_prompt(p, today: str) -> str:
    goals = "\n".join(f"- {g}" for g in p.daily_goals)
    return (
        f"Today is {today}. Draft a broad daily plan for {p.name}.\n"
        f"Their goals for today:\n{goals}\n\n"
        f"Return 5-8 activities in order, each as a short string "
        f"(e.g. 'open the café at 8am', 'restock pastries'). "
        f"Don't include hour-by-hour granularity; just the arc of the day."
    )


# ---------- Per-tick action decision ----------

class ActionDecision(BaseModel):
    reasoning: str = Field(description="One-sentence justification")
    action: Literal["move", "speak", "idle"]
    target_location: str | None = Field(
        default=None, description="location id if action=move, else null"
    )
    target_person: str | None = Field(
        default=None, description="persona id if action=speak, else null"
    )
    activity: str = Field(
        description="Short description of what the persona is doing this tick "
        "(e.g. 'walking to the café', 'wiping down the counter', 'greeting Klaus')"
    )


def action_prompt(
    p,
    current_time: str,
    current_location_name: str,
    adjacent_locations: list[tuple[str, str]],  # [(id, name)]
    others_here: list[tuple[str, str]],          # [(id, name)]
    others_elsewhere: list[tuple[str, str, str]],  # [(id, name, location_name)]
    daily_plan: list[str],
    recent_memory: list[str],
) -> str:
    adj = "\n".join(f"  - {lid}: {name}" for lid, name in adjacent_locations) or "  (none)"
    here = ", ".join(f"{name} ({pid})" for pid, name in others_here) or "no one"
    elsewhere = (
        "\n".join(f"  - {name} ({pid}) at {loc}" for pid, name, loc in others_elsewhere)
        or "  (none visible)"
    )
    plan_lines = "\n".join(f"  - {a}" for a in daily_plan)
    mem_lines = "\n".join(f"  - {m}" for m in recent_memory) or "  (nothing notable)"
    return (
        f"Current sim time: {current_time}\n"
        f"You are at: {current_location_name}\n"
        f"Also here: {here}\n"
        f"Visible elsewhere:\n{elsewhere}\n"
        f"Reachable locations in one tick:\n{adj}\n\n"
        f"Your daily plan:\n{plan_lines}\n\n"
        f"Relevant memories:\n{mem_lines}\n\n"
        f"Decide your next action. Choose one:\n"
        f"  - 'move' to a reachable location (set target_location).\n"
        f"  - 'speak' to someone currently here (set target_person). "
        f"Only pick this if there is a real reason to talk (plan-relevant, "
        f"socially natural, or something in memory makes it apt).\n"
        f"  - 'idle' to continue doing something in place "
        f"(set activity to describe it).\n\n"
        f"Return valid JSON per the schema."
    )


# ---------- Conversation generation ----------

class Utterance(BaseModel):
    speaker: str = Field(description="persona id of the speaker")
    text: str


class Conversation(BaseModel):
    turns: list[Utterance] = Field(description="4-8 turns alternating between the two speakers")
    summary: str = Field(description="One-sentence summary from a neutral narrator")


def conversation_prompt(
    initiator,
    target,
    location_name: str,
    initiator_context: list[str],
    target_context: list[str],
    opening_reason: str,
    recent_chats: list[str] | None = None,
) -> str:
    def ctx(lines: list[str]) -> str:
        return "\n".join(f"  - {m}" for m in lines) or "  (no salient memories)"

    prior_block = ""
    if recent_chats:
        prior_lines = "\n".join(f"  - {c}" for c in recent_chats)
        prior_block = (
            f"\n--- Prior conversations between them (DO NOT repeat the same "
            f"topics or greetings) ---\n{prior_lines}\n"
        )

    return (
        f"Two people have just come together at {location_name} and are about to talk.\n\n"
        f"--- Initiator: {initiator.name} ({initiator.id}) ---\n"
        f"Traits: {initiator.innate}\n"
        f"Background: {initiator.learned}\n"
        f"Currently: {initiator.currently}\n"
        f"What they're thinking about:\n{ctx(initiator_context)}\n\n"
        f"--- Other: {target.name} ({target.id}) ---\n"
        f"Traits: {target.innate}\n"
        f"Background: {target.learned}\n"
        f"Currently: {target.currently}\n"
        f"What they're thinking about:\n{ctx(target_context)}\n"
        f"{prior_block}\n"
        f"Reason the initiator started talking: {opening_reason}\n\n"
        f"Write a natural 4-8 turn conversation alternating between "
        f"{initiator.id} and {target.id}. Start with {initiator.id}. "
        f"Keep each turn 1-2 sentences. End the conversation when it feels natural — "
        f"don't force a resolution. Also return a one-sentence neutral summary.\n\n"
        f"IMPORTANT: If prior conversations are listed above, do NOT re-introduce "
        f"yourselves or ask the same questions. Build on what was already discussed, "
        f"or move to a new topic.\n\n"
        f"Use persona ids ({initiator.id}, {target.id}) as 'speaker' values."
    )


# ---------- Reflection ----------

class FocalPoints(BaseModel):
    questions: list[str] = Field(description="3 high-level questions the persona is implicitly asking")


class Insights(BaseModel):
    insights: list[str] = Field(
        description="3-5 high-level insights the persona has about themselves, "
        "others, or their situation, grounded in the evidence provided"
    )


def focal_points_prompt(p, recent_memory: list[str]) -> str:
    mem = "\n".join(f"  - {m}" for m in recent_memory)
    return (
        f"Given these recent events and thoughts for {p.name}:\n{mem}\n\n"
        f"What are 3 high-level questions {p.name} would implicitly be "
        f"asking themselves right now? Return as a JSON list."
    )


def insights_prompt(p, question: str, evidence: list[str]) -> str:
    ev = "\n".join(f"  {i+1}. {m}" for i, m in enumerate(evidence))
    return (
        f"{p.name} is implicitly asking: \"{question}\"\n\n"
        f"Evidence from their recent memories:\n{ev}\n\n"
        f"What are 3-5 high-level insights {p.name} can draw from this evidence? "
        f"Each insight should be specific, grounded in the evidence, "
        f"and in {p.name}'s voice (first person is fine)."
    )
