#!/usr/bin/env python
"""Render a short demo mp4 of the E3 button desk (no model needed).

    python scripts/desk_demo.py

A scripted playout of the pipeline: a button lights; the commander (human stand-in)
issues an order; the executor grounds it; the character reaches and presses — in time
when executor+reach <= the window W, missing when W is too short. Writes
outputs/desk_demo.mp4 + a repo-root copy (for GitLab Pages). Illustrative; numbers
mirror the L0 run.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                         # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation  # noqa: E402
from matplotlib.patches import Circle                   # noqa: E402

BUTTON_X = [0.34, 0.66]            # two buttons on the panel (left, right)
NAMES = ["red", "blue"]
COLOURS = ["#d73027", "#4575b4"]
DT = 40                            # ms per frame
DESK_Y = 0.74                      # panel height (character reaches up to it)
CX = 0.50                          # character centre x
SHOULDER = (0.58, 0.38)           # right shoulder (where the active arm starts)
REST_HAND = (0.64, 0.26)          # hand resting in the lap

# (lit index, window W ms, executor latency ms, reach ms)
ROUNDS = [
    (1, 900, 80, 520),            # right, fits -> success
    (0, 900, 80, 520),            # left, fits -> success
    (1, 500, 80, 520),            # right, 600>500 -> MISS (window too short)
    (0, 900, 80, 520),            # left, success
]


def _lerp(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def _frames():
    out = []
    for rnd, (lit, W, lat, reach) in enumerate(ROUNDS, 1):
        target = (BUTTON_X[lit], DESK_Y)
        total = 600 + W + 500
        t = 0
        while t < total:
            hand, litidx, color = REST_HAND, None, "#333"
            label = f"Round {rnd}  ·  panel dark — waiting"
            if t >= 600:
                tt = t - 600
                hit = (lat + reach) <= W
                litidx = lit if (tt < W or (hit and tt < lat + reach + 250)) else None
                if tt < lat:
                    label = f"Round {rnd}  ·  W={W}ms  ·  executor grounding the order… ({lat}ms)"
                else:
                    frac = min(1.0, (tt - lat) / reach) if reach else 1.0
                    hand = _lerp(REST_HAND, target, frac)
                    if hit and tt >= lat + reach:
                        color, litidx = "#1a9850", lit
                        label = f"Round {rnd}  ·  PRESSED in {lat+reach}ms  ✓  (W={W}ms)"
                    elif (not hit) and tt >= W:
                        color = "#d73027"
                        label = f"Round {rnd}  ·  MISSED — needed {lat+reach}ms > {W}ms  ✗"
                    else:
                        label = f"Round {rnd}  ·  W={W}ms  ·  character reaching ({reach}ms)"
            rem = max(0.0, (W - (t - 600)) / W) if t >= 600 else 1.0
            out.append({"hand": hand, "lit": litidx, "label": label, "color": color, "rem": rem})
            t += DT
    return out


def main() -> None:
    frames = _frames()
    fig, ax = plt.subplots(figsize=(8, 4.2))

    def draw(i):
        f = frames[i]
        ax.clear()
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        # panel + buttons
        ax.plot([0.08, 0.92], [DESK_Y, DESK_Y], color="#999", lw=10, solid_capstyle="round")
        for j, bx in enumerate(BUTTON_X):
            on = f["lit"] == j
            ax.add_patch(Circle((bx, DESK_Y), 0.05, facecolor=("#ffd400" if on else "#ededed"),
                                edgecolor=COLOURS[j], lw=2.5, zorder=3))
            ax.text(bx, DESK_Y + 0.10, NAMES[j], ha="center", va="center", fontsize=9, color=COLOURS[j])
        # character: head, neck, torso, shoulders, static left arm, active right arm + hand
        ax.add_patch(Circle((CX, 0.46), 0.05, facecolor="#fff", edgecolor="#333", lw=2, zorder=4))
        ax.plot([CX, CX], [0.41, 0.38], color="#333", lw=3)                 # neck
        ax.plot([CX, CX], [0.16, 0.38], color="#333", lw=3)                 # torso
        ax.plot([CX - 0.08, CX + 0.08], [0.38, 0.38], color="#333", lw=3)   # shoulders
        ax.plot([CX - 0.08, CX - 0.17], [0.38, 0.25], color="#333", lw=3)   # resting left arm
        hx, hy = f["hand"]
        ax.plot([SHOULDER[0], hx], [SHOULDER[1], hy], color="#333", lw=3, zorder=4)  # active arm
        ax.add_patch(Circle((hx, hy), 0.022, facecolor=f["color"], edgecolor="none", zorder=5))  # hand
        ax.text(0.5, 0.95, f["label"], ha="center", va="center", fontsize=11)
        ax.barh(0.02, 0.84 * f["rem"], left=0.08, height=0.025, color="#999")  # window countdown
        return []

    anim = FuncAnimation(fig, draw, frames=len(frames), interval=DT, blit=False)
    from pathlib import Path
    out = Path("outputs"); out.mkdir(exist_ok=True)
    dst = out / "desk_demo.mp4"
    anim.save(str(dst), writer=FFMpegWriter(fps=int(1000 / DT), bitrate=900))
    plt.close(fig)
    Path("desk_demo.mp4").write_bytes(dst.read_bytes())
    print(f"wrote {dst} and ./desk_demo.mp4 ({dst.stat().st_size} bytes, {len(frames)} frames)")


if __name__ == "__main__":
    main()
