"""Capture a video (webm/mp4) of the web player replaying a run.

Uses Playwright's built-in screen recording. Outputs webm by default;
if ffmpeg is available, also converts to mp4.

Usage:
    python scripts/capture_video.py --run cafe-morning-v2
    python scripts/capture_video.py --run cafe-morning-v2 --tick-ms 800
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

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
    parser.add_argument("--tick-ms", type=int, default=1200, help="ms per tick in playback")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--width", type=int, default=1100)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--loops", type=int, default=1, help="How many full loops to record")
    args = parser.parse_args()

    if not _SAFE_NAME.match(args.run):
        print(f"ERROR: invalid run name '{args.run}'", file=sys.stderr)
        return 1
    events_file = ROOT / "output" / "runs" / args.run / "events.json"
    if not events_file.exists():
        print(f"ERROR: {events_file} not found.", file=sys.stderr)
        return 1

    # Ensure web/data has the events
    web_data = ROOT / "web" / "data" / args.run
    web_data.mkdir(parents=True, exist_ok=True)
    shutil.copy(events_file, web_data / "events.json")

    import json
    tick_count = len(json.loads(events_file.read_text(encoding="utf-8"))["ticks"])

    from playwright.sync_api import sync_playwright

    server = serve(args.port)
    time.sleep(0.7)

    out_dir = ROOT / "output" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport={"width": args.width, "height": args.height},
                record_video_dir=str(out_dir),
                record_video_size={"width": args.width, "height": args.height},
            )
            page = context.new_page()

            # Use loop=0 so playback ends cleanly; autoplay=1 to start immediately
            url = (
                f"http://localhost:{args.port}/"
                f"?run={args.run}&tickMs={args.tick_ms}&loop=0&autoplay=1"
            )
            page.goto(url)

            # Wait for data to load
            page.wait_for_function("document.getElementById('sim-clock').textContent !== '—'", timeout=10000)

            # Total recording time: loops * ticks * tickMs + buffer
            one_loop_ms = tick_count * args.tick_ms + 2000  # +2s settle
            total_ms = one_loop_ms * args.loops
            print(f"Recording {tick_count} ticks x {args.loops} loop(s) = ~{total_ms // 1000}s ...")

            page.wait_for_timeout(total_ms)

            page.close()
            context.close()
            browser.close()

        # Playwright saves as .webm with an auto-generated name. Find it.
        webm_files = sorted(out_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not webm_files:
            print("ERROR: No video file was created.", file=sys.stderr)
            return 1

        webm_path = webm_files[0]
        final_webm = out_dir / f"{args.run}.webm"
        webm_path.rename(final_webm)
        print(f"Wrote {final_webm}")

        # Try converting to mp4 if ffmpeg is available
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            mp4_path = out_dir / f"{args.run}.mp4"
            print("Converting to mp4 ...")
            subprocess.run(
                [ffmpeg, "-y", "-i", str(final_webm), "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", "-crf", "23", str(mp4_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if mp4_path.exists():
                print(f"Wrote {mp4_path}")
            else:
                print("ffmpeg conversion failed; webm is still available.")
        else:
            print("(ffmpeg not found - install it to auto-convert to mp4)")

    finally:
        server.terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())
