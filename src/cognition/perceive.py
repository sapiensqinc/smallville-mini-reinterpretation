"""Perception: who/what is around the persona this tick.

Much simpler than the paper's vision_r + attention bandwidth, because our
world is a graph of discrete locations rather than a tile grid. We return:
  - the persona's current Location
  - other personas at the same location
  - other personas at adjacent locations (for awareness, not interaction)

This also updates spatial memory with any newly observed location descriptions.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..agent import Persona
from ..world import Location, World


@dataclass
class Perception:
    here: Location
    adjacent: list[Location]
    others_here: list[Persona]
    others_elsewhere: list[tuple[Persona, Location]]


def perceive(persona: Persona, world: World, all_personas: list[Persona]) -> Perception:
    here = world.location(persona.scratch.current_location)
    adjacent = world.adjacent(here.id)

    persona.s_mem.learn(here.id, here.description)
    for loc in adjacent:
        persona.s_mem.learn(loc.id, loc.description)

    others_here: list[Persona] = []
    others_elsewhere: list[tuple[Persona, Location]] = []
    for other in all_personas:
        if other.id == persona.id:
            continue
        other_loc = other.scratch.current_location
        if other_loc == here.id:
            others_here.append(other)
        elif any(a.id == other_loc for a in adjacent):
            others_elsewhere.append((other, world.location(other_loc)))

    return Perception(
        here=here,
        adjacent=adjacent,
        others_here=others_here,
        others_elsewhere=others_elsewhere,
    )
