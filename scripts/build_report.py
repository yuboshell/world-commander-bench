#!/usr/bin/env python
"""Assemble the full report: a baseline run, the output-schema overlay, and the
model-size overlay (read from outputs/model_*.json produced by serve_sweep.sh).

    python scripts/build_report.py --commands 90 --publish

Schemas are run live against the served model; model-size results are loaded from
disk (each size is served separately by serve_sweep.sh). One report.html with all
sections.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arena.config import load_config           # noqa: E402
from arena.harness import run_session          # noqa: E402
from arena.metrics import miss_rate            # noqa: E402
from arena.model_client import RealClient      # noqa: E402
from arena.recorder import Recorder            # noqa: E402
from arena import viz                          # noqa: E402
from schema_sweep import build_schema_table    # noqa: E402

Shim = namedtuple("Shim", "latency_ms targets")
SIZE_ORDER = {"0.6B": 0.6, "1.7B": 1.7, "4B": 4, "8B": 8, "14B": 14, "32B": 32}


def _median(xs):
    return statistics.median(xs) if xs else 0.0


def load_model_results(outdir: Path) -> list[dict]:
    res = []
    for jf in outdir.glob("model_*.json"):
        d = json.loads(jf.read_text())
        frames = [Shim(r["lat"], [None] * r["nt"]) for r in d["rows"]]
        res.append({"name": d["label"], "frames": frames, "report": d["report"]})
    res.sort(key=lambda r: SIZE_ORDER.get(r["name"], 999))
    return res


def model_table(results: list[dict], tick_ms: int) -> str:
    rows = ""
    for r in results:
        alll = [f.latency_ms for f in r["frames"]]
        multi = [f.latency_ms for f in r["frames"] if len(f.targets) >= 2]
        rep = r["report"]
        rows += (
            f"<tr><td>{r['name']}</td><td>{rep['grounding_accuracy']:.2f}</td>"
            f"<td>{_median(alll):.0f} ms</td><td>{miss_rate(alll, tick_ms):.2f}</td>"
            f"<td>{_median(multi):.0f} ms</td><td>{miss_rate(multi, tick_ms):.2f}</td></tr>"
        )
    return ("<table>\n<tr><th>model</th><th>grounding</th><th>p50 latency</th>"
            f"<th>miss@{tick_ms}ms</th><th>multi p50</th><th>multi miss@{tick_ms}ms</th></tr>\n"
            f"{rows}</table>")


def main() -> None:
    cfg = load_config()
    p = argparse.ArgumentParser()
    p.add_argument("--commands", type=int, default=90)
    p.add_argument("--grid", type=int, default=cfg.grid)
    p.add_argument("--agents", type=int, default=cfg.agents)
    p.add_argument("--npcs", type=int, default=cfg.npcs)
    p.add_argument("--tick-ms", type=int, default=cfg.tick_ms)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--outdir", type=str, default="outputs")
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # --- schema sweep (live, against the served model) ---
    sresults, base_rec, base_m = [], None, None
    for name in ("json", "pairs", "grouped"):
        client = RealClient(cfg.base_url, cfg.api_key, cfg.model, schema=name)
        rec = Recorder()
        m = run_session(client, grid=args.grid, agents=args.agents, npcs=args.npcs,
                        tick_ms=args.tick_ms, n_commands=args.commands, seed=args.seed,
                        recorder=rec)
        sresults.append({"name": name, "frames": rec.frames, "metrics": m})
        print(f"[schema {name}] {m.report()}")
        if name == "json":
            base_rec, base_m = rec, m
    s_overlay = viz.plot_schema_frontiers(
        sresults, args.tick_ms, outdir / "schema_frontier.png",
        suptitle="Output-schema comparison — frontier per schema", legend_title="schema")

    # --- model-size overlay (from disk) ---
    mresults = load_model_results(outdir)
    schema_intro = (
        "<p>A language model writes its reply one <b>output token</b> at a time "
        "(a token is a short chunk of text, very roughly &frac34; of a word), one "
        "forward pass each, so <b>latency grows with the number of output tokens</b>. "
        "An <b>output schema</b> is the format we require the reply to take (a "
        "system-prompt instruction plus a parser). Same task, fewer tokens out, "
        "lower latency. We compare three:</p>\n"
        "<ul>\n"
        "<li><b>json</b> (verbose baseline): <code>[{&quot;agent&quot;:&quot;red&quot;,"
        "&quot;dir&quot;:&quot;N&quot;}]</code> — explicit keys per move, most tokens.</li>\n"
        "<li><b>pairs</b> (terse): <code>red:N blue:N</code> — one agent:dir token per move.</li>\n"
        "<li><b>grouped</b> (terse, exploits structure): <code>N: red blue</code> — the "
        "direction once, then the agents moving it. Shortest, since every command shares "
        "one direction across its targets.</li>\n"
        "</ul>"
    )
    sections = [{
        "title": "Output-schema comparison", "png": s_overlay, "intro": schema_intro,
        "table": build_schema_table(sresults, args.tick_ms),
        "caption": "Same task, different reply formats. A terser schema emits "
        "fewer output tokens, so its frontier sits to the left. Largest effect on "
        "multi-agent commands. Watch grounding: a format the model follows less "
        "reliably trades accuracy for speed.",
    }]
    if mresults:
        m_overlay = viz.plot_schema_frontiers(
            mresults, args.tick_ms, outdir / "model_frontier.png",
            suptitle="Model-size comparison — frontier per model", legend_title="model")
        sections.append({
            "title": "Model-size comparison", "png": m_overlay,
            "table": model_table(mresults, args.tick_ms),
            "caption": "Same task, different model sizes (verbose JSON schema). "
            "Smaller models lose grounding; on this single-GPU 2080 Ti they are not "
            "much faster (fixed per-call overhead dominates), so size mainly trades "
            "accuracy here. The frontier is hardware-dependent.",
        })

    # --- StarCraft II testbed (if metrics exist) ---
    sc2_files = sorted(outdir.glob("sc2_2s3z_*.jsonl"),
                       key=lambda p: SIZE_ORDER.get(p.stem.replace("sc2_2s3z_", ""), 999))
    sc2_results = []
    for p in sc2_files:
        rows = [json.loads(l) for l in open(p) if l.strip()]
        if rows:
            sc2_results.append({"name": p.stem.replace("sc2_2s3z_", ""), "rows": rows})
    if sc2_results:
        sc2_png = viz.plot_sc2_model_overlay(sc2_results, outdir / "sc2_latency.png")
        trows = ""
        for r in sc2_results:
            lat = [x["latency_ms"] for x in r["rows"]]
            trows += (f"<tr><td>{r['name']}</td><td>{len(r['rows'])}</td>"
                      f"<td>{_median(lat):.0f} ms</td>"
                      f"<td>{statistics.mean(x['tokens_in'] for x in r['rows']):.0f}</td>"
                      f"<td>{miss_rate(lat, 2000):.2f}</td><td>{miss_rate(lat, 5000):.2f}</td></tr>")
        sc2_table = ("<table>\n<tr><th>model</th><th>decisions</th><th>p50 latency</th>"
                     "<th>input tokens (mean)</th><th>miss@2s</th><th>miss@5s</th></tr>\n"
                     f"{trows}</table>")
        sections.append({
            "title": "StarCraft II testbed — decision latency by model size",
            "png": sc2_png, "table": sc2_table,
            "intro": "<p>The same streaming-command core, scaled up to StarCraft II "
            "(LLM-PySC2, headless, our own vLLM on GPU 2). Each decision now carries the "
            "full game state plus unit/ability wiki — <b>~3000 input tokens</b> vs ~200 in "
            "the arena — so a decision takes <b>seconds</b>, not milliseconds. This is the "
            "efficiency wall the program exists to attack.</p>",
            "caption": "First real SC2 numbers (2s3z). Unlike the arena, latency here is "
            "<b>monotone in model size</b> — at ~3000-token context the prefill/compute "
            "scales with the model, so a smaller model is markedly faster (1.7B ≈ 2× faster "
            "than 8B). Every model misses a 2 s deadline; even the fastest needs several "
            "seconds. Win-rate is not yet meaningful (camera calibration is capped to reach "
            "the LLM, so centering is imperfect) and the clock is synchronous (the game "
            "waits for the model). Latency and token counts are valid measurements.",
        })

    # --- body from the json baseline run ---
    rep = base_m.report()
    png = viz.plot_metrics(rep, base_m.latencies_ms, base_rec.frames,
                           args.tick_ms, outdir / "metrics.png")
    frontier = viz.plot_deadline_frontier(base_rec.frames, args.tick_ms,
                                          outdir / "frontier.png")
    uris = viz.frame_data_uris(base_rec.frames, args.grid)
    meta = {"model": cfg.model, "grid": args.grid, "agents": args.agents,
            "npcs": args.npcs, "tick_ms": args.tick_ms, "seed": args.seed}
    html = viz.build_html_report(rep, png, uris, outdir / "report.html", meta,
                                 base_rec.frames, frontier_png=frontier,
                                 extra_sections=sections)
    print(f"wrote {html}")

    if args.publish:
        repo = Path(__file__).resolve().parent.parent
        copies = [(outdir / "report.html", "report.html"),
                  (outdir / "metrics.png", "assets/metrics.png"),
                  (outdir / "frontier.png", "assets/frontier.png"),
                  (s_overlay, "assets/schema_frontier.png")]
        if mresults:
            copies.append((outdir / "model_frontier.png", "assets/model_frontier.png"))
        if (outdir / "sc2_latency.png").exists():
            copies.append((outdir / "sc2_latency.png", "assets/sc2_latency.png"))
        for src, dst in copies:
            (repo / dst).write_bytes(Path(src).read_bytes())
        subprocess.run(["bash", "scripts/publish_report.sh"], cwd=repo, check=True)


if __name__ == "__main__":
    main()
