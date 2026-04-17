"""Build a self-contained HTML file that works when opened directly (file://).

Inlines style.css, app.js, and events.json into a single HTML file.
The result loops the simulation playback like a GIF — no server needed.

Usage:
    python scripts/build_standalone.py --run cafe-morning-v2
    # -> output/cafe-morning-v2.html  (just double-click to open)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _sanitize_name(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise SystemExit(f"ERROR: invalid run name '{name}' (alphanumeric, -, _ only)")
    return name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="Run name (matches output/runs/<name>/)")
    parser.add_argument("--tick-ms", type=int, default=1200, help="ms per tick")
    parser.add_argument("--pause-ms", type=int, default=2000, help="ms pause between loops")
    args = parser.parse_args()

    run_name = _sanitize_name(args.run)
    events_path = ROOT / "output" / "runs" / run_name / "events.json"
    if not events_path.exists():
        print(f"ERROR: {events_path} not found.", file=sys.stderr)
        return 1

    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    events_json = events_path.read_text(encoding="utf-8")

    # Validate JSON
    json.loads(events_json)

    out_path = (ROOT / "output" / f"{run_name}.html").resolve()
    if not str(out_path).startswith(str((ROOT / "output").resolve())):
        print("ERROR: output path escapes project directory.", file=sys.stderr)
        return 1

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>smallville_2026 — {args.run}</title>
    <style>
{css}
    </style>
  </head>
  <body>
    <header id="topbar">
      <div id="run-name">—</div>
      <div id="sim-clock">—</div>
      <div id="tick-indicator">tick 0 / 0</div>
    </header>
    <nav id="controls">
      <button id="btn-prev" title="Previous tick">&#9664;&#9664;</button>
      <button id="btn-play" title="Play / Pause">&#9654;</button>
      <button id="btn-next" title="Next tick">&#9654;&#9654;</button>
      <input id="scrubber" type="range" min="0" max="0" value="0" />
      <select id="speed">
        <option value="2400">0.5x</option>
        <option value="1200" selected>1x</option>
        <option value="600">2x</option>
        <option value="300">4x</option>
      </select>
    </nav>
    <main>
      <aside id="locations-panel">
        <h2>Locations</h2>
        <ul id="locations-list"></ul>
      </aside>
      <section id="timeline">
        <div id="events"></div>
      </section>
    </main>
    <script>
      window.__embedded_data = {events_json};
    </script>
    <script>
{js}
    </script>
  </body>
</html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size // 1024} KB)")
    print("Double-click to open - loops automatically, no server needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
