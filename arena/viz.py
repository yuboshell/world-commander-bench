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


def build_html_report(report: dict, metrics_png: str | Path,
                      frame_uris: list[str], out_path: str | Path,
                      title: str = "World Commander — arena run") -> Path:
    """Write a single self-contained HTML page: metrics plot + a frame viewer
    with slider, step buttons, and play/pause at an adjustable speed."""
    out_path = Path(out_path)
    metrics_uri = _data_uri_from_file(metrics_png)
    frames_js = "[\n" + ",\n".join(f'"{u}"' for u in frame_uris) + "\n]"
    summary = (f"{report['commands']} commands · grounding "
               f"{report['grounding_accuracy']:.2f} · deadline miss "
               f"{report['deadline_miss_rate']:.2f} · latency p50 "
               f"{report['latency_ms_p50']:.0f} / p95 {report['latency_ms_p95']:.0f} ms")
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 920px;
         color: #1a1a1a; padding: 0 1rem; }}
  h1 {{ font-size: 1.3rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
  .summary {{ background:#f3f5f7; border-radius:8px; padding:.6rem .9rem; font-size:.95rem; }}
  img.metrics {{ width:100%; border:1px solid #e2e2e2; border-radius:6px; }}
  .viewer {{ text-align:center; }}
  #frame {{ width:440px; max-width:100%; border:1px solid #e2e2e2; border-radius:6px; }}
  .controls {{ display:flex; gap:.5rem; align-items:center; justify-content:center;
               flex-wrap:wrap; margin:.7rem 0; }}
  button {{ font-size:1rem; padding:.3rem .7rem; cursor:pointer; }}
  input[type=range] {{ width:60%; }}
  .hint {{ color:#666; font-size:.85rem; }}
</style></head>
<body>
<h1>{title}</h1>
<div class="summary">{summary}</div>

<h2>Metrics</h2>
<img class="metrics" src="{metrics_uri}" alt="latency metrics">

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
