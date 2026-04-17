"""Working memory: everything that describes the persona *right now*.

Distinguished from associative memory in that this is mutable state, not a
log of events. Matches the paper's split between `scratch.json` and
`associative_memory/*`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scratch:
    # current state
    current_location: str                     # location id
    current_activity: str = "idle"
    chatting_with: str | None = None          # persona id

    # day-level planning
    daily_plan: list[str] = field(default_factory=list)
    plan_generated_for_day: str | None = None  # YYYY-MM-DD

    # conversation cooldown: persona_id -> tick when last chatted
    last_chat_tick: dict[str, int] = field(default_factory=dict)
    chat_cooldown_ticks: int = 3  # must wait this many ticks before chatting same person again

    # reflection trigger
    importance_sum_since_last_reflect: float = 0.0

    def can_chat_with(self, other_id: str, current_tick: int) -> bool:
        last = self.last_chat_tick.get(other_id)
        if last is None:
            return True
        return (current_tick - last) >= self.chat_cooldown_ticks

    def record_chat(self, other_id: str, current_tick: int) -> None:
        self.last_chat_tick[other_id] = current_tick
