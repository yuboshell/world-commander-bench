"""Visualization: metric plots, per-frame grid images, and a self-contained
HTML report (and, optionally, an MP4).

Optional extra — needs matplotlib (MP4 also needs an ffmpeg binary). See
requirements-viz.txt. Kept out of the harness so a plain run imports no
plotting stack.

The grid renderer offsets agents that share a cell (the world has no collision
rule, so markers would otherwise hide each other) and rings the commanded
agent(s) in gold, so a command like "move the red one" always shows a red one.
"""
from __future__ import annotations

import base64
import io
import math
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display on amax41
import matplotlib.pyplot as plt              # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402

from .metrics import miss_rate               # noqa: E402
from .recorder import Frame                  # noqa: E402

_NPC_COLOUR = "0.6"
_COLOUR_ALIASES = {"pink": "deeppink", "cyan": "darkcyan"}


def _agent_colour(name: str, controlled: bool) -> str:
    if not controlled:
        return _NPC_COLOUR
    return _COLOUR_ALIASES.get(name, name)


def _cell_offsets(k: int) -> list[tuple[float, float]]:
    """Where to place k agents that share one cell, so all stay visible."""
    if k == 1:
        return [(0.0, 0.0)]
    r = 0.24
    return [(r * math.cos(2 * math.pi * i / k), r * math.sin(2 * math.pi * i / k))
            for i in range(k)]


def _draw_frame(ax, f: Frame, grid: int) -> None:
    ax.clear()
    ax.set_xlim(-0.5, grid - 0.5)
    ax.set_ylim(grid - 0.5, -0.5)  # origin top-left; N decreases y
    ax.set_xticks(range(grid))
    ax.set_yticks(range(grid))
    ax.grid(True, color="0.9")
    ax.set_aspect("equal")

    # group agents by cell so co-located ones can be fanned out
    cells: dict[tuple[int, int], list[tuple[str, bool]]] = {}
    for name, x, y, controlled in f.after:
        cells.setdefault((x, y), []).append((name, controlled))

    targets = set(f.targets)
    for (x, y), occupants in cells.items():
        for (name, controlled), (dx, dy) in zip(occupants, _cell_offsets(len(occupants))):
            px, py = x + dx, y + dy
            if name in targets:  # gold ring behind the commanded agent
                ax.scatter(px, py, s=620, color="none", edgecolors="gold",
                           linewidths=2.5, zorder=4)
            ax.scatter(px, py, s=300, color=_agent_colour(name, controlled),
                       edgecolors="black", zorder=5)
            ax.text(px, py, name[:1].upper() if controlled else "·",
                    ha="center", va="center", color="white", fontsize=8, zorder=6)

    outcome = "OK grounded" if f.correct else "WRONG"
    if f.missed:
        outcome += " - DEADLINE MISS"
    ax.set_title(f'#{f.step}  "{f.command_text}"\n{outcome}  ({f.latency_ms:.0f} ms)',
                 fontsize=9)


def plot_metrics(report: dict, latencies_ms: list[float], frames: list[Frame],
                 tick_ms: int, out_path: str | Path) -> Path:
    """Two-panel summary: latency distribution + per-command latency timeline."""
    out_path = Path(out_path)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7))

    ax1.hist(latencies_ms, bins=30, color="steelblue", edgecolor="white")
    ax1.axvline(tick_ms, color="crimson", ls="--", lw=1.5, label=f"tick budget {tick_ms} ms")
    for label, val in (("mean", report["latency_ms_mean"]),
                       ("p50", report["latency_ms_p50"]),
                       ("p95", report["latency_ms_p95"])):
        ax1.axvline(val, color="black", ls=":", lw=1, alpha=0.6)
        ax1.text(val, ax1.get_ylim()[1] * 0.78, f" {label} {val:.0f}",
                 fontsize=8, rotation=90, va="top")
    ax1.set_xlabel("command-to-action latency (ms)")
    ax1.set_ylabel("commands")
    ax1.set_title(
        f"Latency distribution — {report['commands']} commands "
        f"(grounding {report['grounding_accuracy']:.2f}, "
        f"deadline miss {report['deadline_miss_rate']:.2f})"
    )
    ax1.legend(fontsize=8)

    steps = [f.step for f in frames]
    lat = [f.latency_ms for f in frames]
    missed = [f.missed for f in frames]
    ax2.scatter([s for s, m in zip(steps, missed) if not m],
                [l for l, m in zip(lat, missed) if not m],
                s=12, color="seagreen", label="on time")
    ax2.scatter([s for s, m in zip(steps, missed) if m],
                [l for l, m in zip(lat, missed) if m],
                s=12, color="crimson", label="deadline miss")
    ax2.axhline(tick_ms, color="crimson", ls="--", lw=1.5)
    ax2.set_xlabel("command # (stream order)")
    ax2.set_ylabel("latency (ms)")
    ax2.set_title("Latency over the command stream")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_deadline_frontier(frames: list[Frame], tick_ms: int,
                           out_path: str | Path) -> Path:
    """Deadline miss rate vs deadline budget, overall and by command type.

    Pure post-hoc: a miss is latency > deadline, so the whole curve comes from
    one run's latencies — no extra inference. The right deadline is the world's
    *time-to-consequence* (how long until inaction is punished), not a fixed tick:
    the x-axis is annotated by operating regime so you can read off whether the
    agent is viable in the human-paced band rather than against one number.
    """
    out_path = Path(out_path)
    deadlines = list(range(100, 2601, 50))
    alll = [f.latency_ms for f in frames]
    single = [f.latency_ms for f in frames if len(f.targets) == 1]
    multi = [f.latency_ms for f in frames if len(f.targets) >= 2]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    # operating regimes by time-to-consequence (illustrative bands, not hard cutoffs)
    ax.axvspan(100, 250, color="crimson", alpha=0.06)
    ax.axvspan(250, 2000, color="seagreen", alpha=0.08)
    ax.axvspan(2000, 2600, color="0.5", alpha=0.05)
    ax.text(175, 0.96, "reflex\n(esports)", ha="center", va="top", fontsize=7, color="crimson")
    ax.text(1100, 0.96, "human-paced (time-to-consequence)", ha="center", va="top",
            fontsize=7.5, color="darkgreen")
    ax.text(2300, 0.96, "relaxed", ha="center", va="top", fontsize=7, color="0.4")
    ax.axhline(0.10, color="0.6", ls=":", lw=1, label="10% acceptable")
    for lats, label, colour in ((alll, "all commands", "black"),
                                (single, "single-target", "seagreen"),
                                (multi, "multi-agent", "crimson")):
        if lats:
            ax.plot(deadlines, [miss_rate(lats, d) for d in deadlines],
                    label=f"{label} (n={len(lats)})", color=colour, lw=2)
    ax.axvline(tick_ms, color="gray", ls="--", lw=1.5,
               label=f"arena tick ({tick_ms} ms)")
    ax.set_xlabel("deadline budget = time-to-consequence (ms)")
    ax.set_ylabel("deadline miss rate")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Deadline frontier — miss rate vs budget, by operating regime")
    ax.grid(True, color="0.92")
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_schema_frontiers(results: list[dict], tick_ms: int,
                          out_path: str | Path, suptitle: str | None = None,
                          legend_title: str = "schema") -> Path:
    """Overlay deadline frontiers for several variants on shared axes.

    Each result is {"name": str, "frames": [Frame-like, ...]} (needs .latency_ms
    and .targets). Two panels: all commands, and multi-agent commands only (where
    output length matters most). Used for both schema and model-size overlays.
    """
    if suptitle is None:
        suptitle = "Frontier per variant"
    out_path = Path(out_path)
    deadlines = list(range(100, 2601, 50))
    colours = ["steelblue", "darkorange", "seagreen", "crimson", "purple"]
    fig, (ax_all, ax_multi) = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)

    for r, colour in zip(results, colours):
        alll = [f.latency_ms for f in r["frames"]]
        multi = [f.latency_ms for f in r["frames"] if len(f.targets) >= 2]
        ax_all.plot(deadlines, [miss_rate(alll, d) for d in deadlines],
                    label=r["name"], color=colour, lw=2)
        if multi:
            ax_multi.plot(deadlines, [miss_rate(multi, d) for d in deadlines],
                          label=r["name"], color=colour, lw=2)

    for ax, title in ((ax_all, "all commands"), (ax_multi, "multi-agent commands")):
        ax.axvline(tick_ms, color="gray", ls="--", lw=1.5)
        ax.set_xlabel("deadline budget (ms)")
        ax.set_title(title)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(True, color="0.92")
        ax.legend(fontsize=8, title=legend_title)
    ax_all.set_ylabel("deadline miss rate")
    fig.suptitle(f"{suptitle}  (dashed = current {tick_ms} ms)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_sc2_latency(rows: list[dict], out_path: str | Path) -> Path:
    """SC2 decision latency: histogram + deadline frontier, from metric rows
    ({latency_ms, tokens_in, tokens_out, ...} per LLM decision)."""
    out_path = Path(out_path)
    lat = [r["latency_ms"] for r in rows]
    deadlines = list(range(250, 10001, 250))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    ax1.hist(lat, bins=20, color="indianred", edgecolor="white")
    ax1.axvline(statistics.median(lat), color="black", ls=":", lw=1,
                label=f"p50 {statistics.median(lat):.0f} ms")
    for d, lab in ((500, "0.5 s"), (2000, "2 s")):
        ax1.axvline(d, color="gray", ls="--", lw=1)
        ax1.text(d, ax1.get_ylim()[1] * 0.9, f" {lab}", fontsize=8, rotation=90, va="top")
    ax1.set_xlabel("decision latency (ms)")
    ax1.set_ylabel("decisions")
    ax1.set_title("SC2 decision latency")
    ax1.legend(fontsize=8)

    ax2.plot(deadlines, [miss_rate(lat, d) for d in deadlines], color="crimson", lw=2)
    ax2.axvline(2000, color="gray", ls="--", lw=1, label="2 s")
    ax2.set_xlabel("deadline budget (ms)")
    ax2.set_ylabel("deadline miss rate")
    ax2.set_ylim(-0.02, 1.02)
    ax2.set_title("SC2 deadline frontier")
    ax2.grid(True, color="0.92")
    ax2.legend(fontsize=8)

    ti = statistics.mean(r["tokens_in"] for r in rows)
    fig.suptitle(f"StarCraft II — {len(rows)} decisions, ~{ti:.0f} input tokens each")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_sc2_model_overlay(results: list[dict], out_path: str | Path) -> Path:
    """Overlay SC2 deadline frontiers per model size. results = [{name, rows}],
    rows = metric dicts with latency_ms. Left: miss-vs-budget per model. Right:
    p50 latency by model (latency is monotone in size at SC2 context scale)."""
    out_path = Path(out_path)
    deadlines = list(range(250, 10001, 250))
    colours = ["seagreen", "steelblue", "crimson", "darkorange", "purple"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.3))

    p50s = []
    for r, c in zip(results, colours):
        lat = [x["latency_ms"] for x in r["rows"]]
        ax1.plot(deadlines, [miss_rate(lat, d) for d in deadlines],
                 label=f"{r['name']} (n={len(lat)})", color=c, lw=2)
        p50s.append((r["name"], statistics.median(lat), c))
    ax1.axvline(2000, color="gray", ls="--", lw=1.5, label="2 s")
    ax1.set_xlabel("deadline budget (ms)")
    ax1.set_ylabel("deadline miss rate")
    ax1.set_ylim(-0.02, 1.02)
    ax1.set_title("SC2 deadline frontier per model")
    ax1.grid(True, color="0.92")
    ax1.legend(fontsize=8, title="model")

    ax2.bar([n for n, _, _ in p50s], [v for _, v, _ in p50s],
            color=[c for _, _, c in p50s])
    ax2.set_ylabel("p50 decision latency (ms)")
    ax2.set_title("SC2 p50 latency by model size")
    ax2.grid(True, axis="y", color="0.92")

    fig.suptitle("StarCraft II — latency vs model size (~3000-token context)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_rate_frontier(models: list[dict], deadline_ms: float, out_path: str | Path,
                       title: str = "Command-stream load — deadline misses vs arrival rate") -> Path:
    """Per-model load curves: x = command arrival rate (Hz). Left: % of commands
    that produced no on-time action (late or dropped). Right: p95 response time
    (queue wait + service). Each model's service rate (1/mean-latency) is drawn as
    a vertical dotted line — the knee where backlog starts to run away."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.3))
    for m in models:
        rows = m["rows"]
        x = [r["rate_hz"] for r in rows]
        ax1.plot(x, [r["unmet_rate"] * 100 for r in rows], marker=".", label=m["label"])
        color = ax1.lines[-1].get_color()
        ax1.axvline(m["service_hz"], color=color, ls=":", alpha=0.5)
        ax2.plot(x, [r["p95_response_ms"] for r in rows], marker=".", color=color, label=m["label"])
    ax1.set_xlabel("command arrival rate (Hz)")
    ax1.set_ylabel("unmet commands (%)")
    ax1.set_title(f"Deadline misses (deadline {deadline_ms:.0f} ms)")
    ax1.set_ylim(-2, 102)
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8, title="model (dotted = its service rate)")
    ax2.axhline(deadline_ms, color="k", ls="--", alpha=0.5, label=f"deadline {deadline_ms:.0f} ms")
    ax2.set_xlabel("command arrival rate (Hz)")
    ax2.set_ylabel("p95 response (ms, log)")
    ax2.set_title("Tail response under load")
    ax2.set_yscale("log")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend(fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return Path(out_path)


def frame_data_uris(frames: list[Frame], grid: int, max_frames: int = 200) -> list[str]:
    """Render each frame to a small PNG and return base64 data: URIs."""
    fig, ax = plt.subplots(figsize=(4.2, 4.6))
    uris: list[str] = []
    for f in frames[:max_frames]:
        _draw_frame(ax, f, grid)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=90)
        uris.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
    plt.close(fig)
    return uris


def _data_uri_from_file(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def _segment_stats(frames: list[Frame]) -> tuple[int, float, float]:
    """(count, mean latency ms, deadline-miss rate) for a subset of frames."""
    n = len(frames)
    if not n:
        return 0, 0.0, 0.0
    return (n,
            statistics.mean(f.latency_ms for f in frames),
            sum(f.missed for f in frames) / n)


def build_html_report(report: dict, metrics_png: str | Path,
                      frame_uris: list[str], out_path: str | Path,
                      meta: dict, frames: list[Frame],
                      frontier_png: str | Path | None = None,
                      extra_sections: list[dict] | None = None,
                      title: str = "World Commander — benchmark report (command arena + StarCraft II)") -> Path:
    """Write a single, self-explanatory HTML report: what the experiment is, the
    run configuration, every metric defined, a grid legend, the charts explained,
    and an interactive replay (slider / step / play at an adjustable speed)."""
    out_path = Path(out_path)
    metrics_uri = _data_uri_from_file(metrics_png)
    frames_js = "[\n" + ",\n".join(f'"{u}"' for u in frame_uris) + "\n]"

    frontier_section = ""
    if frontier_png is not None:
        frontier_uri = _data_uri_from_file(frontier_png)
        frontier_section = (
            "<h2>Deadline frontier</h2>\n"
            f'<img class="metrics" src="{frontier_uri}" alt="deadline frontier">\n'
            '<p class="hint">A deadline miss is simply <i>latency &gt; deadline</i>, so this '
            "whole curve is computed post-hoc from one run — no extra inference. The right "
            "deadline is the world’s <b>time-to-consequence</b> (how long until inaction is "
            "punished), not a fixed tick, so the x-axis is shaded by operating regime. The "
            f"{meta.get('tick_ms','?')} ms tick (dashed) is misleadingly harsh: it sits in the "
            "steep part of the curve. Slide right into the <b>human-paced</b> band (voice-issued "
            "command, consequences seconds away) and the miss rate collapses — at ~1 s the fast "
            "models miss essentially nothing. So the real question is not “can it beat a game "
            "clock” but <b>at what time-to-consequence the agent stays viable, and how cheaply</b>; "
            "the frontier shifts left with a smaller model, a terser schema, and a faster GPU.</p>"
        )

    # extra comparison sections, each {title, png, table (html), caption}
    extra_sections_html = ""
    for sec in (extra_sections or []):
        uri = _data_uri_from_file(sec["png"])
        extra_sections_html += (
            f"<h2>{sec['title']}</h2>\n"
            f"{sec.get('intro', '')}\n"          # raw HTML, rendered before the figure
            f'<img class="metrics" src="{uri}" alt="{sec["title"]}">\n'
            f"{sec.get('table', '')}\n"
            f'<p class="hint">{sec.get("caption", "")}</p>\n'
        )

    summary = (f"{report['commands']} commands &middot; grounding "
               f"<b>{report['grounding_accuracy']:.2f}</b> &middot; deadline miss "
               f"<b>{report['deadline_miss_rate']:.2f}</b> &middot; latency p50 "
               f"<b>{report['latency_ms_p50']:.0f}</b> / p95 "
               f"<b>{report['latency_ms_p95']:.0f}</b> ms")

    # command-type breakdown across the three forms
    single = [f for f in frames if len(f.targets) == 1]
    allexcept = [f for f in frames if "except" in f.command_text.lower()]
    subset = [f for f in frames if len(f.targets) >= 2 and "except" not in f.command_text.lower()]
    rows_spec = [
        ("single-target", "“Move the red agent north.”", single),
        ("positive subset", "“Move the blue and green agents north.”", subset),
        ("all-except group", "“Every agent except the red one, move north.”", allexcept),
    ]
    cmdtype_rows = ""
    for label, example, fs in rows_spec:
        if not fs:
            continue
        n, lat, miss = _segment_stats(fs)
        cmdtype_rows += (
            f"<tr><td>{label}<br><span class='hint'>{example}</span></td>"
            f"<td>{n}</td><td>{lat:.0f} ms</td><td>{miss:.2f}</td></tr>"
        )

    m = meta
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 920px;
         color: #1a1a1a; line-height: 1.5; padding: 0 1rem; }}
  h1 {{ font-size: 1.4rem; margin-bottom: .2rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2.2rem; border-bottom: 1px solid #eee; padding-bottom: .2rem; }}
  .summary {{ background:#f3f5f7; border-radius:8px; padding:.7rem 1rem; font-size:1rem; }}
  table {{ border-collapse: collapse; margin:.6rem 0; font-size:.92rem; }}
  th, td {{ border:1px solid #e3e3e3; padding:.35rem .6rem; text-align:left; vertical-align:top; }}
  th {{ background:#f7f8fa; }}
  dl {{ margin:.4rem 0; }} dt {{ font-weight:600; margin-top:.5rem; }} dd {{ margin:0 0 .2rem 1rem; }}
  img.metrics {{ width:100%; border:1px solid #e2e2e2; border-radius:6px; }}
  .legend {{ list-style:none; padding:0; }}
  .legend li {{ margin:.25rem 0; }}
  .dot {{ display:inline-block; width:.85rem; height:.85rem; border-radius:50%;
          border:1px solid #333; vertical-align:middle; margin-right:.4rem; }}
  .ring {{ display:inline-block; width:.85rem; height:.85rem; border-radius:50%;
           border:3px solid gold; vertical-align:middle; margin-right:.4rem; }}
  .viewer {{ text-align:center; }}
  #frame {{ width:460px; max-width:100%; border:1px solid #e2e2e2; border-radius:6px; }}
  .controls {{ display:flex; gap:.5rem; align-items:center; justify-content:center;
               flex-wrap:wrap; margin:.7rem 0; }}
  button {{ font-size:1rem; padding:.3rem .7rem; cursor:pointer; }}
  input[type=range] {{ width:60%; }}
  .hint {{ color:#666; font-size:.85rem; }}
  footer {{ margin-top:3rem; color:#777; font-size:.82rem; border-top:1px solid #eee; padding-top:.6rem; }}
</style></head>
<body>
<h1>{title}</h1>
<p class="hint">Natural-language command of agents in real time, under a latency budget. Phase-1 warm-up of the World Commander program.</p>

<p>Below is the arena in motion: coloured agents follow streamed natural-language
orders while grey agents wander on their own clock. <b>Press Play</b> (or drag
the slider) to watch what happens — then read on for what is measured.</p>

<h2>Grid replay <span class="hint">(you control the speed — drag the slider or press Play)</span></h2>
<div class="viewer">
  <img id="frame" alt="grid frame">
  <div class="controls">
    <button id="prev">◀ Prev</button>
    <button id="play">▶ Play</button>
    <button id="next">Next ▶</button>
    <label>speed
      <select id="speed">
        <option value="2000">slow (0.5/s)</option>
        <option value="1000" selected>1/s</option>
        <option value="500">2/s</option>
        <option value="250">fast (4/s)</option>
      </select>
    </label>
  </div>
  <input id="slider" type="range" min="0" value="0">
  <div class="hint">command <span id="idx">0</span> / <span id="total">0</span></div>
</div>

<h2>How to read the grid</h2>
<ul class="legend">
  <li><span class="dot" style="background:red"></span><span class="dot" style="background:blue"></span><span class="dot" style="background:green"></span><span class="dot" style="background:gold"></span>
      <b>Coloured agents</b> — the ones you command (red, blue, green, yellow). The letter is the colour’s initial.</li>
  <li><span class="dot" style="background:#999"></span><b>Grey agents</b> — uncontrolled NPCs (marked “·”). They move one random step every tick on their own clock; you cannot command them. They are what makes a late command cost something.</li>
  <li><span class="ring"></span><b>Gold ring</b> — the agent(s) the current command targets.</li>
  <li><b>Fanned-out markers in one cell</b> — several agents on the same square (the world has no collision rule), spread apart so none is hidden.</li>
  <li><b>Axes</b> — x is the column (0–{int(m.get('grid',1))-1}, left→right), y is the row (top→bottom); “north” decreases y. The title shows the command, whether it was grounded, and its latency.</li>
</ul>

<h2>What this is</h2>
<p>The <b>command arena</b> is a minimal grid world that stress-tests one thing:
can a language model turn streamed natural-language orders into the right moves
<i>fast enough to matter</i>. Each step, one order is issued (e.g.
“Move the red agent north”); the model reads the world state and replies with the
moves. One order is trivial by design — the test is the <b>stream</b>, many and
fast. Crucially the clock <b>never pauses</b>: the grey agents move on their own
every step, so a late command concedes ground, exactly as a slow decision
concedes to an opponent in a real game.</p>

<h2>Results at a glance</h2>
<div class="summary">{summary}</div>
<p class="hint"><b>Grounding</b> is whether the moves were correct; <b>deadline
miss</b> is whether they arrived within the tick budget. The model is accurate
but often late — the definitions and the per-command-type breakdown below show
where the time goes.</p>

<h2>Run configuration</h2>
<table>
  <tr><th>Model</th><td>{m.get('model','?')}</td></tr>
  <tr><th>Grid</th><td>{m.get('grid','?')} × {m.get('grid','?')}</td></tr>
  <tr><th>Controlled agents</th><td>{m.get('agents','?')} (colour-tagged: red, blue, green, yellow)</td></tr>
  <tr><th>Uncontrolled agents (NPCs)</th><td>{m.get('npcs','?')} (grey; move one random step each tick)</td></tr>
  <tr><th>Tick budget</th><td>{m.get('tick_ms','?')} ms — the per-command deadline</td></tr>
  <tr><th>Commands in this run</th><td>{report['commands']}</td></tr>
  <tr><th>Seed</th><td>{m.get('seed','?')} (world + command stream are reproducible)</td></tr>
</table>

<h2>Metrics — what each number means</h2>
<dl>
  <dt>Grounding accuracy</dt>
  <dd>Fraction of commands where the model’s move set <b>exactly matches</b> the
      ground-truth move set (right agents, right direction). Measures
      understanding, independent of speed.</dd>
  <dt>Command-to-action latency</dt>
  <dd>Wall-clock time (ms) from issuing the command to the model returning its
      action. Reported as mean, median (p50), and 95th percentile (p95).</dd>
  <dt>Deadline miss rate</dt>
  <dd>Fraction of commands whose latency exceeded the <b>{m.get('tick_ms','?')} ms tick budget</b>.
      A late action is <b>dropped</b> — it simply does not happen — and the world
      ticks on regardless. This is the real-time penalty: correct but late still loses.</dd>
</dl>
<p class="hint"><b>Why {m.get('tick_ms','?')} ms?</b> It is a real-time commander
cadence — about two decisions per second, matching screenshot-driven VLM
commanders for StarCraft II such as AVA (~2&nbsp;Hz). It is deliberately one
operating point, not a hard truth: a single deadline that everything passes (or
fails) measures nothing, whereas {m.get('tick_ms','?')} ms is discriminating here.
The right deliverable is the whole <i>deadline frontier</i> below — performance vs
budget — of which any single deadline is just one vertical slice.</p>

<h2>Latency by command type</h2>
<p>The arena issues three command forms: single-target, a positively named
multi-agent subset (“the blue and green agents”), and the all-except group.
Multi-agent orders name more agents, so the model emits more tokens and takes
longer — the usual source of a high-latency cluster.</p>
<table>
  <tr><th>Command type</th><th>count</th><th>mean latency</th><th>deadline miss</th></tr>
  {cmdtype_rows}
</table>

<h2>The charts</h2>
<img class="metrics" src="{metrics_uri}" alt="latency metrics">
<p class="hint"><b>Top — latency distribution.</b> Histogram of per-command
latency. The dashed red line is the {m.get('tick_ms','?')} ms tick budget;
everything to its right is a deadline miss. Dotted lines mark mean / p50 / p95.
A split (bimodal) shape means two populations of commands — typically fast
single-target vs slower multi-agent orders.<br>
<b>Bottom — latency over the stream.</b> One dot per command in issue order;
green = on time, red = deadline miss. Shows whether misses are scattered or
clustered as the stream runs.</p>

{frontier_section}

{extra_sections_html}

<script>
const FRAMES = {frames_js};
const img = document.getElementById('frame');
const slider = document.getElementById('slider');
const idx = document.getElementById('idx');
const total = document.getElementById('total');
const playBtn = document.getElementById('play');
const speed = document.getElementById('speed');
let i = 0, timer = null;
slider.max = FRAMES.length - 1;
total.textContent = FRAMES.length - 1;
function show(n) {{
  i = (n + FRAMES.length) % FRAMES.length;
  img.src = FRAMES[i]; slider.value = i; idx.textContent = i;
}}
function stop() {{ if (timer) {{ clearInterval(timer); timer = null; playBtn.textContent = '▶ Play'; }} }}
function play() {{
  stop();
  timer = setInterval(() => {{ if (i >= FRAMES.length - 1) {{ stop(); return; }} show(i + 1); }},
                      parseInt(speed.value, 10));
  playBtn.textContent = '⏸ Pause';
}}
document.getElementById('prev').onclick = () => {{ stop(); show(i - 1); }};
document.getElementById('next').onclick = () => {{ stop(); show(i + 1); }};
playBtn.onclick = () => timer ? stop() : play();
slider.oninput = () => {{ stop(); show(parseInt(slider.value, 10)); }};
speed.onchange = () => {{ if (timer) play(); }};
show(0);
</script>

<footer>
World Commander — Phase-1 command arena. Model: {m.get('model','?')}.
Self-contained report (images and frames embedded); regenerate with
<code>scripts/visualize.py</code>. Grounding/latency are real measurements; a
late action is dropped under the unpausable clock.
</footer>
</body></html>
"""
    out_path.write_text(html)
    return out_path


def render_replay(frames: list[Frame], grid_size: int, tick_ms: int,
                  out_path: str | Path, fps: int = 2, max_frames: int = 200) -> Path:
    """Optional MP4 export (opt-in). Reuses the shared frame renderer."""
    out_path = Path(out_path)
    frames = frames[:max_frames]
    fig, ax = plt.subplots(figsize=(6, 6.6))
    anim = FuncAnimation(fig, lambda i: _draw_frame(ax, frames[i], grid_size),
                         frames=len(frames), interval=1000 // fps)
    anim.save(str(out_path), writer=FFMpegWriter(fps=fps, bitrate=1800))
    plt.close(fig)
    return out_path
