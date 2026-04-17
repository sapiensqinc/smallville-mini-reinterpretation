"""Spatial memory: what the persona has learned about the world.

In the original paper this was a hierarchical tree (world→sector→arena→object).
Our world is already a flat location graph, so spatial memory here just
tracks which locations the persona has visited and their descriptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SpatialMemory:
    known_locations: dict[str, str] = field(default_factory=dict)  # id -> description

    def learn(self, location_id: str, description: str) -> None:
        self.known_locations[location_id] = description

    def knows(self, location_id: str) -> bool:
        return location_id in self.known_locations
