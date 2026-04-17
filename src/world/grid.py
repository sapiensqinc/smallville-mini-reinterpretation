"""Location graph. Replaces the paper's 2D tile map + pathfinder.

A persona is always at exactly one location. `adjacency` defines which
locations are reachable in a single tick — no multi-step pathfinding,
which is fine because our tick is ~10 sim-minutes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Location:
    id: str
    name: str
    description: str


class World:
    def __init__(
        self,
        name: str,
        description: str,
        locations: list[Location],
        adjacency: dict[str, list[str]],
    ):
        self.name = name
        self.description = description
        self._locations = {loc.id: loc for loc in locations}
        self._adjacency = adjacency

    def location(self, lid: str) -> Location:
        return self._locations[lid]

    def all_locations(self) -> list[Location]:
        return list(self._locations.values())

    def adjacent(self, lid: str) -> list[Location]:
        return [self._locations[nid] for nid in self._adjacency.get(lid, [])]

    def can_move(self, src: str, dst: str) -> bool:
        return dst in self._adjacency.get(src, [])
