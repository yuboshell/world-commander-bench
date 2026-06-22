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
            "caption": "Controlled back-to-back runs on a dedicated GPU 2. 4B is the "
            "sweet spot — top grounding and lowest latency; below 4B grounding "
            "collapses (0.41–0.54) and latency is actually <b>worse</b> (output is "
            "~2.5 tokens for every model, so the small ones are not rambling — they "
            "just run slower kernels). 8B matches 4B for no gain; 14B-AWQ will not serve "
            "on one 2080 Ti. The frontier is hardware-dependent.",
        })

        # --- command-stream load curve (replays model latencies, no extra GPU) ---
        from arena.rate import load_curve
        rate_models, services = [], []
        for r in mresults:
            lat = [f.latency_ms for f in r["frames"]]
            svc = 1000.0 / (sum(lat) / len(lat))
            services.append(svc)
            rate_models.append({"label": r["name"], "service_hz": svc, "_lat": lat})
        lo, hi = 0.2 * min(services), 2.0 * max(services)
        rates = [lo + i * (hi - lo) / 24 for i in range(25)]
        rate_deadline = 2000.0
        for rm in rate_models:
            rm["rows"] = load_curve(rm["_lat"], rates, rate_deadline)
            ok = [row["rate_hz"] for row in rm["rows"] if row["unmet_rate"] <= 0.1]
            rm["sustainable_hz"] = max(ok) if ok else 0.0
        rate_models.sort(key=lambda m: m["service_hz"], reverse=True)
        rate_png = viz.plot_rate_frontier(rate_models, rate_deadline,
                                          outdir / "rate_frontier.png")
        rrows = "".join(
            f"<tr><td>{m['label']}</td><td>{m['service_hz']:.2f} Hz</td>"
            f"<td>{m['sustainable_hz']:.2f} Hz</td></tr>" for m in rate_models)
        rate_table = ("<table>\n<tr><th>model</th><th>service rate (1/mean latency)</th>"
                      "<th>sustainable rate (&le;10% unmet @2s)</th></tr>\n"
                      f"{rrows}</table>")
        sections.append({
            "title": "Command-stream load — how fast can commands arrive?",
            "png": rate_png,
            "intro": "<p>The arena's real test is the <b>stream</b>: commands arrive at "
            "some rate while one model serves them one at a time. Arriving faster than the "
            "model answers, they <b>queue</b> — and a command's deadline runs from "
            "when it <b>arrived</b>, not when the model reached it. We replay each model's "
            "recorded latencies through a single-server queue (<code>arena/rate.py</code>) "
            "at rising arrival rates — no extra GPU.</p>",
            "table": rate_table,
            "caption": "Left: share of commands with no on-time action (late or dropped) "
            "vs arrival rate; each dotted line is a model's service rate, where backlog "
            "runs away. Right: p95 response (queue wait + service). Sustainable command "
            "rate tracks model speed (~2 Hz for 4B/8B). Shown at a generous 2 s deadline "
            "to isolate the load limit; at the arena's 500 ms deadline per-command latency "
            "already binds.",
        })

    # --- macro vs micro capability curve (from representation_cap_*.json) ---
    cap_files = sorted(outdir.glob("representation_cap_*.json"))
    if cap_files:
        micro_g = {r["name"]: r["report"]["grounding_accuracy"] for r in mresults}
        pts = []
        for cf in cap_files:
            d = json.loads(cf.read_text())
            lab = d["tag"].replace("cap_", "")
            if lab not in SIZE_ORDER:
                continue
            row = d["rows"][0]
            pts.append({"label": lab, "size": SIZE_ORDER[lab], "micro": micro_g.get(lab, 1.0),
                        "macro_pa": row["grounding_per_agent"],
                        "macro_pc": row["grounding_per_command"], "lat_p50": row["lat_p50"]})
        if pts:
            cap_png = viz.plot_macro_capability(pts, outdir / "macro_capability.png")
            crows = "".join(
                f"<tr><td>{p['label']}</td><td>{p['micro']:.2f}</td><td>{p['macro_pa']:.2f}</td>"
                f"<td>{p['macro_pc']:.2f}</td><td>{p['lat_p50']:.0f} ms</td></tr>"
                for p in sorted(pts, key=lambda p: p["size"]))
            sections.append({
                "title": "Macro vs micro — specific vs abstract commands",
                "png": cap_png,
                "table": ("<table>\n<tr><th>model</th><th>micro grounding</th>"
                          "<th>macro (per-agent)</th><th>macro (per-command)</th>"
                          f"<th>macro p50 latency</th></tr>\n{crows}</table>"),
                "intro": "<p>Commands span two levels — specific vs abstract — through one channel. "
                "<b>Micro</b> names agents explicitly (\"move the red agent north\") — "
                "reference resolution. <b>Macro</b> is a goal whose per-agent moves must be "
                "computed from the world (\"everyone toward the center\", \"flee the nearest "
                "enemy\") — spatial planning. Macro is scored per-agent on fresh random "
                "states (n=200): the fraction of agents sent in a progress-making direction.</p>",
                "caption": "Micro <b>saturates at 4B</b> (1.00) — the efficiency sweet spot. "
                "Macro instead <b>climbs with size and is never solved</b>: 1.7B can't do it, "
                "4B≈8B plateau near a random valid move (~0.35), 14B reaches 0.59 but lands a "
                "whole command only ~1 in 5. So macro is capability-bound and buys capability "
                "with latency (right) — reintroducing the tradeoff micro escaped. The "
                "bottleneck for macro is reasoning, not the clock.",
            })

    # --- hierarchy router (from hierarchy.json) ---
    hf = outdir / "hierarchy.json"
    if hf.exists():
        h = json.loads(hf.read_text())
        hrows = "".join(
            f"<tr><td>{p['policy']}</td><td>{p['grounding']:.2f}</td>"
            f"<td>{p['p50_lat']:.0f} ms</td><td>{p['micro_grounding']:.2f}</td>"
            f"<td>{p['macro_grounding']:.2f}</td></tr>" for p in h["policies"])
        sections.append({
            "title": "Hierarchy router — micro→small, macro→large",
            "png": None,
            "intro": "<p>The macro-capability curve motivates a hierarchy: micro is solved "
            "cheaply by a small model, macro needs the big (slow) one. Route each command to the "
            "right model; compare over one fixed half-micro/half-macro stream "
            f"(n={h['commands']}, fresh states). small={h['small_model']}, large={h['large_model']}.</p>",
            "table": ("<table>\n<tr><th>policy</th><th>grounding</th><th>p50 latency</th>"
                      "<th>micro grounding</th><th>macro grounding</th></tr>\n" + hrows + "</table>"),
            "caption": "The router matches large-only's grounding at lower latency — it pays the "
            "big model only for macro and serves micro fast on the small one. A Pareto win; the "
            f"gain grows with the micro fraction (here 50/50). Preliminary (n={h['commands']}).",
        })

    # --- efficiency levers: context length + prefix cache (from json) ---
    cl = outdir / "context_latency.json"
    pc = outdir / "prefix_cache.json"
    if cl.exists():
        c = json.loads(cl.read_text())
        clrows = "".join(f"<tr><td>{r['prompt_tokens']}</td><td>{r['lat_p50']:.0f} ms</td></tr>"
                         for r in c["rows"])
        pcnote = ""
        if pc.exists():
            p = json.loads(pc.read_text())
            pcnote = (f" Prefix-caching an SC2-scale static prefix (~{p['prefix_tokens']} tokens) "
                      f"cuts a decision from <b>{p['uncached_p50']:.0f} ms to {p['cached_p50']:.0f} ms</b> "
                      f"(~{p['saving_ms']:.0f} ms saved).")
        sections.append({
            "title": "Efficiency levers — context length & prefix caching",
            "png": None,
            "intro": "<p>Decision latency vs input context (fixed short output; prefix cache OFF, "
            "unique prompts → true prefill cost). Input context is a real but ~linear, "
            "<b>cacheable</b> cost; the bigger latency driver is output length × decode speed.</p>",
            "table": ("<table>\n<tr><th>input tokens</th><th>latency (p50)</th></tr>\n"
                      + clrows + "</table>"),
            "caption": "Prefill is ~linear in context (~0.2 ms/token here)." + pcnote +
            " So for SC2: cache the static system+wiki prefix and keep output terse — both attack "
            "latency directly, while input-context reduction mainly helps the VRAM budget.",
        })

    # --- granularity spectrum + macro decomposition (from json) ---
    gg = outdir / "granularity_grid.json"
    idj = outdir / "intent_decompose.json"
    if gg.exists():
        g = json.loads(gg.read_text())
        grows = "".join(f"<tr><td>{r['granularity']}</td><td>{r['grounding_per_agent']:.2f}</td>"
                        f"<td>{r['lat_p50']:.0f} ms</td></tr>" for r in g["rows"])
        note = ""
        if idj.exists():
            d = json.loads(idj.read_text())
            note = (f" And intent classification (order→primitive) is <b>{d['accuracy']:.2f}</b> "
                    "on 4B — so macro via <b>classify-then-code-execute ≈ that</b>, vs ~0.38 when "
                    "the LLM does the geometry. Don't make the LLM plan geometry: it's perfect at "
                    "intent and reference; put deterministic geometry in code.")
        sections.append({
            "title": "Command types — from naming a unit to setting a goal",
            "png": None,
            "intro": "<p>The four command types, 4B on fresh states: <b>micro</b> (name a unit — "
            "\"the red agent\"), <b>region</b> (describe by location — \"the top half\"), <b>memory</b> "
            "(refer back in time — \"the ones I sent west earlier\"), <b>macro</b> (set a goal — "
            "\"everyone toward the centre\"). The first three are different ways to <i>refer</i> to "
            "units; the last asks the model to <i>plan</i>. Per-agent acceptable-set grounding.</p>",
            "table": ("<table>\n<tr><th>command type</th><th>grounding</th><th>p50 latency</th>"
                      f"</tr>\n{grows}</table>"),
            "caption": "Reference — named, spatial, <b>and temporal</b> — is solved (~0.97–1.00); "
            "only goal planning (~0.37) is the cliff. So it's planning, not perception/memory/"
            "spatial grounding, that's hard." + note,
        })

    # (E3 embodiment lives on its own page: scripts/build_desk_report.py -> embodiment.html)

    # (E2 StarCraft II lives on its own page: sc2.html — the decision-latency-by-model-size
    #  section was moved there via scripts/sc2_latency_block.py. The grid arena (E1) report
    #  stays focused on the arena + efficiency story.)

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
