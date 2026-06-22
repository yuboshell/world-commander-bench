#!/usr/bin/env python
"""Render a short demo mp4 of the E3 button desk (no model needed).

    python scripts/desk_demo.py

A scripted playout: each round a button lights for a window W; the LLM grounds it
(brief), then the hand slides over and presses — succeeding when decide+reach <= W,
missing when the window is too short. Writes outputs/desk_demo.mp4 + repo-root copy
(for GitLab Pages). Purely illustrative; the numbers mirror the L0 run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                         # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation  # noqa: E402

REST_X = 0.10
BUTTON_X = [0.38, 0.78]            # two buttons (left, right)
NAMES = ["red", "blue"]
DT = 40                            # ms per frame

# (lit index, window W ms, llm latency ms, reach ms) — reach ~ |rest-button|*scale
ROUNDS = [
    (1, 900, 80, 700),            # right, fits (780<=900) -> success
    (0, 900, 80, 300),            # left, fits -> success
    (1, 500, 80, 700),            # right, 780>500 -> MISS (window too short)
    (0, 900, 80, 300),            # left, success
]


def _frames():
    out = []
    for rnd, (lit, W, lat, reach) in enumerate(ROUNDS, 1):
        bx = BUTTON_X[lit]
        total = 500 + W + 500
        t = 0
        while t < total:
            hand, litidx, color = REST_X, None, "#444"
            label = f"Round {rnd}  ·  dark (waiting)"
            if t >= 500:
                tt = t - 500
                hit = (lat + reach) <= W
                litidx = lit if (tt < W or (hit and tt < lat + reach + 200)) else None
                if tt < lat:
                    label = f"Round {rnd}  ·  W={W}ms  ·  LLM grounding… ({lat}ms)"
                else:
                    frac = min(1.0, (tt - lat) / reach) if reach else 1.0
                    hand = REST_X + (bx - REST_X) * frac
                    if hit and tt >= lat + reach:
                        color, litidx = "#1a9850", lit
                        label = f"Round {rnd}  ·  PRESSED in {lat+reach}ms  ✓  (W={W}ms)"
                    elif (not hit) and tt >= W:
                        color = "#d73027"
                        label = f"Round {rnd}  ·  MISSED — needed {lat+reach}ms > {W}ms  ✗"
                    else:
                        label = f"Round {rnd}  ·  W={W}ms  ·  reaching ({reach}ms)"
            out.append({"hand": hand, "lit": litidx, "label": label, "color": color, "W": W,
                        "rem": max(0.0, (W - (t - 500)) / W) if t >= 500 else 1.0})
            t += DT
    return out


def main() -> None:
    frames = _frames()
    fig, ax = plt.subplots(figsize=(8, 3.2))

    def draw(i):
        f = frames[i]
        ax.clear()
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        ax.plot([0.05, 0.95], [0.55, 0.55], color="#bbb", lw=8, solid_capstyle="round")  # desk
        for j, bx in enumerate(BUTTON_X):
            on = f["lit"] == j
            ax.scatter([bx], [0.55], s=1400, c=("#ffd400" if on else "#e6e6e6"),
                       edgecolors="#888", zorder=3)
            ax.text(bx, 0.55, NAMES[j], ha="center", va="center", fontsize=8, zorder=4)
        ax.scatter([f["hand"]], [0.30], s=500, c=f["color"], zorder=5)   # hand
        ax.plot([f["hand"], f["hand"]], [0.30, 0.46], color=f["color"], lw=2, zorder=4)
        ax.text(0.5, 0.92, f["label"], ha="center", va="center", fontsize=11)
        ax.barh(0.08, 0.9 * f["rem"], left=0.05, height=0.03, color="#888")  # window countdown
        return []

    anim = FuncAnimation(fig, draw, frames=len(frames), interval=DT, blit=False)
    out = Path("outputs"); out.mkdir(exist_ok=True)
    dst = out / "desk_demo.mp4"
    anim.save(str(dst), writer=FFMpegWriter(fps=int(1000 / DT), bitrate=800))
    plt.close(fig)
    (Path("desk_demo.mp4")).write_bytes(dst.read_bytes())   # repo-root copy for Pages
    print(f"wrote {dst} and ./desk_demo.mp4 ({dst.stat().st_size} bytes, {len(frames)} frames)")


if __name__ == "__main__":
    main()
