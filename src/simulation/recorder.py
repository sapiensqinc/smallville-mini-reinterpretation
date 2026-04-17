"""Event recorder — writes the tick-by-tick log that the web player consumes.

Schema of output events.json:
{
  "meta": {
    "run_name": str,
    "start_time": iso str,
    "seconds_per_tick": int,
    "personas": [ {id, name, icon, home} ],
    "locations": [ {id, name, description} ]
  },
  "ticks": [
    {
      "tick": int,
      "time": iso str,
      "personas": [ {id, location, activity} ],
      "events": [
        {type: "move"|"action"|"chat"|"reflect", actor, ...}
      ]
    }
  ]
}
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..agent import Persona
from ..world import World


class Recorder:
    def __init__(self, run_name: str, out_dir: Path):
        self.run_name = run_name
        self.out_dir = out_dir
        self.meta: dict = {}
        self.ticks: list[dict] = []

    def set_meta(
        self,
        *,
        start_time: datetime,
        seconds_per_tick: int,
        personas: list[Persona],
        world: World,
    ) -> None:
        self.meta = {
            "run_name": self.run_name,
            "start_time": start_time.isoformat(),
            "seconds_per_tick": seconds_per_tick,
            "world": {"name": world.name, "description": world.description},
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "icon": p.icon,
                    "home": p.home,
                }
                for p in personas
            ],
            "locations": [
                {"id": loc.id, "name": loc.name, "description": loc.description}
                for loc in world.all_locations()
            ],
        }

    def record_tick(
        self,
        *,
        tick: int,
        time: datetime,
        personas: list[Persona],
        events: list[dict],
    ) -> None:
        self.ticks.append(
            {
                "tick": tick,
                "time": time.isoformat(),
                "personas": [
                    {
                        "id": p.id,
                        "location": p.scratch.current_location,
                        "activity": p.scratch.current_activity,
                    }
                    for p in personas
                ],
                "events": events,
            }
        )

    def flush(self) -> Path:
        run_dir = self.out_dir / self.run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        events_path = run_dir / "events.json"
        with events_path.open("w", encoding="utf-8") as f:
            json.dump(
                {"meta": self.meta, "ticks": self.ticks},
                f,
                indent=2,
                ensure_ascii=False,
            )
        return events_path
