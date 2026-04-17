"""Generate a synthetic events.json so you can verify the web UI without
spending any Gemini credits.

Writes to:
  output/runs/demo/events.json
  web/data/demo/events.json

Then open: http://localhost:8000/?run=demo
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    start = datetime(2026, 4, 16, 7, 30)
    seconds_per_tick = 600

    meta = {
        "run_name": "demo",
        "start_time": start.isoformat(),
        "seconds_per_tick": seconds_per_tick,
        "world": {
            "name": "Hobbs Café neighborhood, morning (DEMO)",
            "description": "Hand-crafted synthetic data. No Gemini calls were made.",
        },
        "personas": [
            {"id": "isabella", "name": "Isabella Rodriguez", "icon": "👩‍🍳", "home": "isabella_home"},
            {"id": "klaus", "name": "Klaus Mueller", "icon": "🧑‍🎓", "home": "klaus_home"},
            {"id": "maria", "name": "Maria Lopez", "icon": "🧑‍💻", "home": "maria_home"},
        ],
        "locations": [
            {"id": "hobbs_cafe", "name": "Hobbs Café", "description": ""},
            {"id": "park", "name": "Johnson Park", "description": ""},
            {"id": "isabella_home", "name": "Isabella's apartment", "description": ""},
            {"id": "klaus_home", "name": "Klaus's apartment", "description": ""},
            {"id": "maria_home", "name": "Maria's apartment", "description": ""},
        ],
    }

    # Build a small scripted scene: everyone heads toward the café, Isabella
    # and Klaus chat about the Valentine's party, Klaus later reflects.
    ticks = []
    state = {"isabella": "isabella_home", "klaus": "klaus_home", "maria": "maria_home"}
    activity = {
        "isabella": "getting dressed",
        "klaus": "still in bed",
        "maria": "working on problem set",
    }

    def tick(i, events):
        ticks.append({
            "tick": i,
            "time": (start + timedelta(seconds=seconds_per_tick * i)).isoformat(),
            "personas": [
                {"id": k, "location": v, "activity": activity[k]} for k, v in state.items()
            ],
            "events": events,
        })

    tick(0, [
        {"type": "action", "actor": "isabella", "text": "getting dressed"},
        {"type": "action", "actor": "klaus", "text": "still in bed, staring at the ceiling"},
        {"type": "action", "actor": "maria", "text": "working on quantum mechanics problem set"},
    ])

    state["isabella"] = "hobbs_cafe"; activity["isabella"] = "opening the café, flipping chairs down"
    tick(1, [
        {"type": "move", "actor": "isabella", "from": "isabella_home", "to": "hobbs_cafe", "text": "heading down to open up"},
        {"type": "action", "actor": "klaus", "text": "finally getting up, craving coffee"},
        {"type": "action", "actor": "maria", "text": "stretching, deciding on a coffee break"},
    ])

    state["klaus"] = "hobbs_cafe"; activity["klaus"] = "ordering at the counter"
    tick(2, [
        {"type": "move", "actor": "klaus", "from": "klaus_home", "to": "hobbs_cafe", "text": "walking to the café"},
        {"type": "action", "actor": "isabella", "text": "wiping down the counter"},
        {"type": "action", "actor": "maria", "text": "packing her notebook"},
    ])

    tick(3, [
        {"type": "chat", "actor": "isabella", "target": "klaus", "text": "Morning, Klaus! The usual drip?"},
        {"type": "chat", "actor": "klaus", "target": "isabella", "text": "Please. I was up late writing — and I could use a whole pot, honestly."},
        {"type": "chat", "actor": "isabella", "target": "klaus", "text": "That bad? Listen — I'm putting together a small Valentine's thing here next Friday. Low-key. You should stop by."},
        {"type": "chat", "actor": "klaus", "target": "isabella", "text": "Oh — really? I almost never go to those, but... yeah, maybe. Thanks for thinking of me."},
        {"type": "chat", "actor": "isabella", "target": "klaus", "text": "Bring someone if you want. No pressure."},
        {"type": "chat", "actor": "klaus", "target": "isabella", "text": "I'll think about it. Anyway — this coffee is a lifesaver."},
    ])

    state["maria"] = "hobbs_cafe"; activity["maria"] = "just arrived, spotting Klaus"
    tick(4, [
        {"type": "move", "actor": "maria", "from": "maria_home", "to": "hobbs_cafe", "text": "walking in with a half-finished problem set"},
        {"type": "action", "actor": "isabella", "text": "ringing up Klaus's order"},
        {"type": "action", "actor": "klaus", "text": "settling at a window table"},
    ])

    tick(5, [
        {"type": "chat", "actor": "maria", "target": "klaus", "text": "Klaus! I need a break from operators. Mind if I join?"},
        {"type": "chat", "actor": "klaus", "target": "maria", "text": "Please, sit. Isabella just invited me to a Valentine's thing here."},
        {"type": "chat", "actor": "maria", "target": "klaus", "text": "Wait, YOU are going to a party? I have to see this."},
        {"type": "chat", "actor": "klaus", "target": "maria", "text": "I said I'd think about it. Don't start."},
    ])

    tick(6, [
        {"type": "action", "actor": "isabella", "text": "restocking pastry case, pleased Klaus didn't say no outright"},
        {"type": "reflect", "actor": "klaus", "text": "People in this neighborhood still invite me to things even when I'm withdrawn — maybe that's a kind of community I've been missing in my dissertation framing."},
        {"type": "action", "actor": "maria", "text": "pulling out her notebook and gently teasing Klaus about the party"},
    ])

    out = {"meta": meta, "ticks": ticks}

    run_path = ROOT / "output" / "runs" / "demo" / "events.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    web_path = ROOT / "web" / "data" / "demo" / "events.json"
    web_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(run_path, web_path)

    print(f"Wrote {run_path}")
    print(f"Wrote {web_path}")
    print("Open: python -m http.server 8000 --directory web")
    print("      http://localhost:8000/?run=demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
