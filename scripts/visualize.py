#!/usr/bin/env python
"""Run a recorded arena session and emit visualizations.

    python scripts/visualize.py --mock --commands 60          # offline
    python scripts/visualize.py --commands 120                # real model

Default output (in <outdir>): metrics.png and a self-contained report.html
(metrics plot + an interactive grid-replay viewer with slider / step / play at
an adjustable speed). Open report.html in a browser — no server needed.

Video is opt-in: --mp4 writes replay.mp4; --upload pushes it to the rclone
Google Drive remote. The default path needs no Drive at all.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.config import load_config           # noqa: E402
from arena.harness import run_session          # noqa: E402
from arena.model_client import MockClient, RealClient   # noqa: E402
from arena.recorder import Recorder            # noqa: E402
from arena import viz                          # noqa: E402


def upload_to_drive(path: Path, remote: str, folder: str) -> str:
    dest = f"{remote}:{folder}"
    subprocess.run(["rclone", "copy", str(path), dest], check=True)
    out = subprocess.run(["rclone", "link", f"{dest}/{path.name}"],
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def main() -> None:
    cfg = load_config()
    p = argparse.ArgumentParser(description="Visualize a command-arena session.")
    p.add_argument("--mock", action="store_true", help="use the no-GPU mock model")
    p.add_argument("--commands", type=int, default=60)
    p.add_argument("--grid", type=int, default=cfg.grid)
    p.add_argument("--agents", type=int, default=cfg.agents)
    p.add_argument("--npcs", type=int, default=cfg.npcs)
    p.add_argument("--tick-ms", type=int, default=cfg.tick_ms)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--outdir", type=str, default="outputs")
    p.add_argument("--mp4", action="store_true", help="also write an MP4 (needs ffmpeg)")
    p.add_argument("--fps", type=int, default=2)
    p.add_argument("--upload", action="store_true", help="push the MP4 to Google Drive (implies --mp4)")
    p.add_argument("--drive-remote", type=str, default="gdrive")
    p.add_argument("--drive-folder", type=str, default="world-commander-bench")
    args = p.parse_args()

    if args.mock:
        client = MockClient()
        print("[mock model — validating the harness, not a real result]")
    else:
        client = RealClient(cfg.base_url, cfg.api_key, cfg.model)
        print(f"[model {cfg.model} @ {cfg.base_url}]")

    rec = Recorder()
    metrics = run_session(
        client, grid=args.grid, agents=args.agents, npcs=args.npcs,
        tick_ms=args.tick_ms, n_commands=args.commands, seed=args.seed,
        recorder=rec,
    )
    report = metrics.report()
    print(report)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    png = viz.plot_metrics(report, metrics.latencies_ms, rec.frames,
                           args.tick_ms, outdir / "metrics.png")
    frontier = viz.plot_deadline_frontier(rec.frames, args.tick_ms,
                                           outdir / "frontier.png")
    uris = viz.frame_data_uris(rec.frames, args.grid)
    meta = {"model": "mock" if args.mock else cfg.model, "grid": args.grid,
            "agents": args.agents, "npcs": args.npcs, "tick_ms": args.tick_ms,
            "seed": args.seed}
    html = viz.build_html_report(report, png, uris, outdir / "report.html",
                                 meta, rec.frames, frontier_png=frontier)
    print(f"wrote {png}\nwrote {frontier}\nwrote {html}")

    if args.mp4 or args.upload:
        mp4 = viz.render_replay(rec.frames, args.grid, args.tick_ms,
                                outdir / "replay.mp4", fps=args.fps)
        print(f"wrote {mp4}")
        if args.upload:
            link = upload_to_drive(mp4, args.drive_remote, args.drive_folder)
            print(f"uploaded MP4 -> link: {link or '(rclone link returned nothing)'}")


if __name__ == "__main__":
    main()
