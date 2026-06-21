#!/usr/bin/env python
"""Render a top-down 'tactical map' demo from per-step raw_units frames saved by
the WCB_SC2_SAVE_FRAMES hook (in the llm_smac bin scripts). Shows EVERY unit
(allies vs enemy), sized by health, with deaths as they vanish — independent of
the in-game camera (which only frames the group the LLM is commanding).

    python scripts/render_sc2_demo.py outputs/frames outputs/render

Then compose with ffmpeg (add captions/title) into the demo clip. This is the
reusable demo renderer: a reviewable artifact for supervising agent runs.
"""
import sys, glob, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# raw_units columns (pysc2 FeatureUnit)
UT, ALLI, HP, SH, X, Y = 0, 1, 2, 3, 12, 13
W = H = 660
M = 70  # margin


def load(framedir):
    return [np.load(f) for f in sorted(glob.glob(os.path.join(framedir, "*.npy")))]


def bbox(frames):
    xs, ys = [], []
    for fr in frames:
        a = fr[fr[:, HP] > 0]
        if len(a):
            xs += list(a[:, X]); ys += list(a[:, Y])
    return (min(xs), max(xs), min(ys), max(ys)) if xs else (0, 1, 0, 1)


def font(sz, bold=True):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/" + ("arialbd.ttf" if bold else "arial.ttf"), sz)
    except Exception:
        return ImageFont.load_default()


def main():
    fd, od = sys.argv[1], sys.argv[2]
    os.makedirs(od, exist_ok=True)
    frames = load(fd)
    if not frames:
        print("no frames found in", fd); return
    x0, x1, y0, y1 = bbox(frames)
    span = max(x1 - x0, y1 - y0, 1.0)

    ox = (W - 2 * M - (x1 - x0) / span * (W - 2 * M)) / 2  # centre the content (keep aspect)
    oy = (H - 2 * M - (y1 - y0) / span * (H - 2 * M)) / 2

    def px(x, y):
        sx = M + ox + (x - x0) / span * (W - 2 * M)
        sy = M + oy + (y - y0) / span * (H - 2 * M)
        return sx, H - sy  # flip y so north is up

    f_hud, f_lab = font(20), font(15, False)
    for i, fr in enumerate(frames):
        img = Image.new("RGB", (W, H), (16, 20, 28))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 36], fill=(10, 13, 19))
        d.text((12, 8), "StarCraft II  3s5z  -  top-down tactical view (every unit)", font=f_lab, fill=(210, 210, 210))
        na = ne = 0
        for u in fr[fr[:, HP] > 0]:
            x, y = px(u[X], u[Y])
            r = max(6, min(17, 6 + float(u[HP]) / 11.0))
            if int(u[ALLI]) == 1:
                col = (70, 200, 255); na += 1      # ally
            elif int(u[ALLI]) == 4:
                col = (255, 85, 70); ne += 1       # enemy
            else:
                col = (150, 150, 150)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(245, 245, 245))
        d.text((12, H - 32), f"Allies (cyan): {na}     Enemy (red): {ne}", font=f_hud, fill=(240, 240, 240))
        img.save(os.path.join(od, f"{i:04d}.png"))
    print(f"rendered {len(frames)} frames -> {od}  (bbox x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}])")


if __name__ == "__main__":
    main()
