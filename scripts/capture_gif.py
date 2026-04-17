"""Capture a GIF of the web player replaying a run.

Strategy:
  1. Start a local static server serving the web/ directory.
  2. Launch headless Chromium via Playwright pointed at the player with
     ?run=<name>&capture=1 — capture mode disables real-time pacing.
  3. The player exposes `window.__sim_total_frames` and a `tickTo(i)` API.
     We step through frames one at a time, screenshotting each, then
     assemble a GIF with imageio.

Usage:
    python scripts/capture_gif.py --run cafe-morning --fps 4
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import imageio.v3 as iio

ROOT = Path(__file__).resolve().parents[1]
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")


def serve(port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", str(ROOT / "web")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--fps", type=int, default=4)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--width", type=int, default=900)
    parser.add_argument("--height", type=int, default=1200)
    args = parser.parse_args()

    if not _SAFE_NAME.match(args.run):
        print(f"ERROR: invalid run name '{args.run}'", file=sys.stderr)
        return 1
    events_file = ROOT / "output" / "runs" / args.run / "events.json"
    if not events_file.exists():
        print(f"ERROR: {events_file} not found. Run the sim first.", file=sys.stderr)
        return 1

    # Copy events.json into web/data/ so the static server can serve it.
    web_data = ROOT / "web" / "data" / args.run
    web_data.mkdir(parents=True, exist_ok=True)
    shutil.copy(events_file, web_data / "events.json")

    from playwright.sync_api import sync_playwright

    server = serve(args.port)
    time.sleep(0.7)  # let the server come up

    frames_dir = Path(tempfile.mkdtemp(prefix="smallville_frames_"))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={"width": args.width, "height": args.height})
            page = context.new_page()
            page.goto(f"http://localhost:{args.port}/?run={args.run}&capture=1")
            page.wait_for_function("window.__sim_ready === true", timeout=15000)
            total = page.evaluate("window.__sim_total_frames")
            print(f"Capturing {total} frames ...")

            frame_paths: list[Path] = []
            for i in range(total):
                page.evaluate(f"window.__sim_tick_to({i})")
                # give the browser one animation frame to paint
                page.wait_for_timeout(80)
                fp = frames_dir / f"frame_{i:04d}.png"
                page.screenshot(path=str(fp))
                frame_paths.append(fp)

            browser.close()

        print("Encoding GIF ...")
        images = [iio.imread(fp) for fp in frame_paths]
        gif_path = ROOT / "output" / "gifs" / f"{args.run}.gif"
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        iio.imwrite(
            gif_path,
            images,
            extension=".gif",
            duration=int(1000 / args.fps),
            loop=0,
        )
        print(f"Wrote {gif_path}")
    finally:
        server.terminate()
        shutil.rmtree(frames_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
