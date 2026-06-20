#!/usr/bin/env python
"""Compare output schemas: run the arena under each, overlay their deadline
frontiers, and fold the comparison into the report.

    python scripts/schema_sweep.py --commands 90 --publish

Runs each schema (json, pairs, grouped) against the served model, builds an
overlay frontier + a comparison table, and regenerates report.html using the
first schema as the primary run plus an "Output-schema comparison" section.
"""
from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.config import load_config           # noqa: E402
from arena.harness import run_session          # noqa: E402
from arena.metrics import miss_rate            # noqa: E402
from arena.model_client import RealClient      # noqa: E402
from arena.recorder import Recorder            # noqa: E402
from arena import viz                          # noqa: E402


def _median(xs):
    return statistics.median(xs) if xs else 0.0


def build_schema_table(results: list[dict], tick_ms: int) -> str:
    rows = ""
    for r in results:
        frames = r["frames"]
        alll = [f.latency_ms for f in frames]
        multi = [f.latency_ms for f in frames if len(f.targets) >= 2]
        rep = r["metrics"].report()
        rows += (
            f"<tr><td>{r['name']}</td>"
            f"<td>{rep['grounding_accuracy']:.2f}</td>"
            f"<td>{_median(alll):.0f} ms</td>"
            f"<td>{miss_rate(alll, tick_ms):.2f}</td>"
            f"<td>{_median(multi):.0f} ms</td>"
            f"<td>{miss_rate(multi, tick_ms):.2f}</td></tr>"
        )
    return (
        "<table>\n<tr><th>schema</th><th>grounding</th>"
        f"<th>p50 latency</th><th>miss@{tick_ms}ms</th>"
        f"<th>multi p50</th><th>multi miss@{tick_ms}ms</th></tr>\n{rows}</table>"
    )


def main() -> None:
    cfg = load_config()
    p = argparse.ArgumentParser(description="Compare output schemas in the arena.")
    p.add_argument("--commands", type=int, default=90)
    p.add_argument("--schemas", type=str, default="json,pairs,grouped")
    p.add_argument("--grid", type=int, default=cfg.grid)
    p.add_argument("--agents", type=int, default=cfg.agents)
    p.add_argument("--npcs", type=int, default=cfg.npcs)
    p.add_argument("--tick-ms", type=int, default=cfg.tick_ms)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--outdir", type=str, default="outputs")
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()

    schemas = [s.strip() for s in args.schemas.split(",") if s.strip()]
    results = []
    for name in schemas:
        client = RealClient(cfg.base_url, cfg.api_key, cfg.model, schema=name)
        rec = Recorder()
        # same seed across schemas -> identical command stream, fair comparison
        m = run_session(client, grid=args.grid, agents=args.agents, npcs=args.npcs,
                        tick_ms=args.tick_ms, n_commands=args.commands, seed=args.seed,
                        recorder=rec)
        results.append({"name": name, "frames": rec.frames, "metrics": m})
        print(f"[{name}] {m.report()}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    overlay = viz.plot_schema_frontiers(results, args.tick_ms, outdir / "schema_frontier.png")
    table = build_schema_table(results, args.tick_ms)

    # primary run = first schema; add the schema-comparison section
    base = results[0]
    rep = base["metrics"].report()
    png = viz.plot_metrics(rep, base["metrics"].latencies_ms, base["frames"],
                           args.tick_ms, outdir / "metrics.png")
    frontier = viz.plot_deadline_frontier(base["frames"], args.tick_ms,
                                          outdir / "frontier.png")
    uris = viz.frame_data_uris(base["frames"], args.grid)
    meta = {"model": cfg.model, "grid": args.grid, "agents": args.agents,
            "npcs": args.npcs, "tick_ms": args.tick_ms, "seed": args.seed}
    html = viz.build_html_report(rep, png, uris, outdir / "report.html", meta,
                                 base["frames"], frontier_png=frontier,
                                 schema_png=overlay, schema_table=table)
    print(f"wrote {overlay}\nwrote {html}")

    if args.publish:
        repo_root = Path(__file__).resolve().parent.parent
        for src, dst in ((outdir / "report.html", "report.html"),
                         (outdir / "metrics.png", "assets/metrics.png"),
                         (outdir / "frontier.png", "assets/frontier.png"),
                         (overlay, "assets/schema_frontier.png")):
            (repo_root / dst).write_bytes(Path(src).read_bytes())
        subprocess.run(["bash", "scripts/publish_report.sh"], cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
