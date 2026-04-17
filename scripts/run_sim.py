"""Run a simulation: load config + scene, run N ticks, write events.json.

Usage:
    python scripts/run_sim.py
    python scripts/run_sim.py --config config.yaml --ticks 20
"""
from __future__ import annotations

import argparse
import logging
import random
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv

ROOT = Path(__file__).resolve().parents[1]
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")
sys.path.insert(0, str(ROOT))


def load_env() -> None:
    """Load GEMINI_API_KEY from .env.local (preferred) or .env.

    We walk up from CWD so a `.env.local` placed in the parent of the project
    (e.g. projects/.env.local) is picked up too.
    """
    for name in (".env.local", ".env"):
        path = find_dotenv(name, usecwd=True)
        if path:
            load_dotenv(path, override=False)

from src.agent import Persona
from src.llm import Embedder, GeminiClient
from src.simulation import Recorder, Simulation
from src.world import Location, World


def load_world(path: Path) -> World:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    locations = [
        Location(id=loc["id"], name=loc["name"], description=loc["description"])
        for loc in data["locations"]
    ]
    return World(
        name=data["name"],
        description=data.get("description", ""),
        locations=locations,
        adjacency=data["adjacency"],
    )


def load_personas(paths: list[Path]) -> list[Persona]:
    out: list[Persona] = []
    for p in paths:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        out.append(Persona.from_config(cfg))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--ticks", type=int, default=None, help="Override max_ticks")
    parser.add_argument("--run-name", default=None, help="Override run name")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    load_env()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = (ROOT / args.config).resolve()
    if not str(config_path).startswith(str(ROOT.resolve())):
        print("ERROR: config path must be within the project directory.", file=sys.stderr)
        return 1
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    run_name = args.run_name or cfg["run"]["name"]
    if not _SAFE_NAME.match(run_name):
        print(f"ERROR: invalid run name '{run_name}' (alphanumeric, -, _ only)", file=sys.stderr)
        return 1
    max_ticks = args.ticks or cfg["run"]["max_ticks"]
    start_time = datetime.fromisoformat(cfg["run"]["start_time"])
    random.seed(cfg["run"].get("seed", 0))

    world = load_world(ROOT / cfg["world"])
    personas = load_personas([ROOT / p for p in cfg["personas"]])

    llm = GeminiClient(model_map=cfg["models"])
    embedder = Embedder(model=cfg["models"]["embedding"])

    recorder = Recorder(run_name=run_name, out_dir=ROOT / "output" / "runs")

    sim = Simulation(
        world=world,
        personas=personas,
        llm=llm,
        embedder=embedder,
        recorder=recorder,
        start_time=start_time,
        seconds_per_tick=cfg["run"]["seconds_per_tick"],
        retrieval_k=cfg["memory"]["retrieval_top_k"],
        recency_decay=cfg["memory"]["recency_decay"],
        reflect_threshold=cfg["memory"]["importance_reflect_threshold"],
    )

    print(f"Running '{run_name}' for {max_ticks} ticks "
          f"({len(personas)} personas, {len(world.all_locations())} locations)")
    sim.run(max_ticks=max_ticks)
    out_path = recorder.flush()
    print(f"Wrote {out_path}")

    # Also copy into web/data/<run>/events.json so the static web player can load it
    web_copy = ROOT / "web" / "data" / run_name / "events.json"
    web_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(out_path, web_copy)
    print(f"Copied to {web_copy} (browser can now load it)")

    print(f"LLM calls: {llm.call_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
