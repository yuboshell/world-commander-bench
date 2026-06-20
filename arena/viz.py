"""Visualization: metric plots (PNG) and a grid-replay animation (MP4).

Optional extra — needs matplotlib (+ ffmpeg for MP4), not part of the light
core. See requirements-viz.txt. Kept separate from the harness so a plain run
never imports a plotting stack.
"""
from __future__ import annotations

import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display on amax41
import matplotlib.pyplot as plt              # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402

from .recorder import Frame                  # noqa: E402

# NPCs render grey; controlled agents use their colour name where matplotlib knows it.
_NPC_COLOUR = "0.6"
_COLOUR_ALIASES = {"pink": "deeppink", "cyan": "darkcyan"}


def _agent_colour(name: str, controlled: bool) -> str:
    if not controlled:
        return _NPC_COLOUR
    return _COLOUR_ALIASES.get(name, name)


def plot_metrics(report: dict, latencies_ms: list[float], frames: list[Frame],
                 tick_ms: int, out_path: str | Path) -> Path:
    """Two-panel summary: latency distribution + per-command latency timeline."""
    out_path = Path(out_path)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7))

    # Panel 1 — latency histogram with the tick budget and key percentiles.
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

    # Panel 2 — per-command latency, coloured by on-time vs missed.
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


def render_replay(frames: list[Frame], grid_size: int, tick_ms: int,
                  out_path: str | Path, fps: int = 3, max_frames: int = 120) -> Path:
    """Render the grid evolving one command per video frame, as an MP4."""
    out_path = Path(out_path)
    frames = frames[:max_frames]
    fig, ax = plt.subplots(figsize=(6, 6.6))

    def draw(i: int) -> None:
        ax.clear()
        f = frames[i]
        ax.set_xlim(-0.5, grid_size - 0.5)
        ax.set_ylim(grid_size - 0.5, -0.5)  # origin top-left; N decreases y
        ax.set_xticks(range(grid_size))
        ax.set_yticks(range(grid_size))
        ax.grid(True, color="0.9")
        ax.set_aspect("equal")
        for name, x, y, controlled in f.after:
            ax.scatter(x, y, s=420, color=_agent_colour(name, controlled),
                       edgecolors="black", zorder=3)
            ax.text(x, y, name[:1].upper() if controlled else "·",
                    ha="center", va="center", color="white", fontsize=9, zorder=4)
        outcome = "✓ grounded" if f.correct else "✗ wrong"
        if f.missed:
            outcome += " · DEADLINE MISS"
        ax.set_title(f"#{f.step}  “{f.command_text}”\n{outcome}  ({f.latency_ms:.0f} ms)",
                     fontsize=10)

    anim = FuncAnimation(fig, draw, frames=len(frames), interval=1000 // fps)
    anim.save(str(out_path), writer=FFMpegWriter(fps=fps, bitrate=1800))
    plt.close(fig)
    return out_path
