"""Persona — the agent.

Holds identity (stable), scratch (mutable state), associative memory (long-term),
and spatial memory. Does not know about LLMs directly — cognition/ modules
take a Persona + a GeminiClient and do work on the persona's memories.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..memory import AssociativeMemory, Scratch, SpatialMemory


@dataclass
class Persona:
    # stable identity
    id: str
    name: str
    age: int
    icon: str                   # emoji or short string for UI
    innate: str
    learned: str
    currently: str
    lifestyle: str
    home: str                   # location id
    daily_goals: list[str]

    # state
    scratch: Scratch = None              # type: ignore[assignment]
    a_mem: AssociativeMemory = field(default_factory=AssociativeMemory)
    s_mem: SpatialMemory = field(default_factory=SpatialMemory)

    @classmethod
    def from_config(cls, cfg: dict) -> "Persona":
        p = cls(
            id=cfg["id"],
            name=cfg["name"],
            age=cfg["age"],
            icon=cfg.get("icon", "🙂"),
            innate=cfg["innate"],
            learned=cfg["learned"],
            currently=cfg["currently"],
            lifestyle=cfg["lifestyle"],
            home=cfg["home"],
            daily_goals=list(cfg.get("daily_goals", [])),
        )
        p.scratch = Scratch(current_location=cfg["initial_location"])
        return p
