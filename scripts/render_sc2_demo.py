#!/usr/bin/env python
"""Top-down tactical demo render from per-step raw_units (saved by the WCB_SC2_SAVE_FRAMES
hook in the llm_smac bin scripts). Reviewable, camera-independent demo of an SC2 game:

  - every unit shown, shaped by TYPE  (Stalker = circle / ranged,  Zealot = square / melee)
  - coloured by SIDE  (allied = cyan,  enemy = red),  sized by current health,  deaths vanish
  - a top band holds the title + legend + live counts; a bottom band is left clear for ffmpeg
    captions, so on-screen text NEVER overlaps the units
  - trailing post-game frames (units flipped to neutral at episode end) are dropped

    python scripts/render_sc2_demo.py outputs/frames outputs/render
"""
import sys, glob, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

UT, ALLI, HP, X, Y = 0, 1, 2, 12, 13          # raw_units columns
STALKER, ZEALOT = 74, 73
W = 720
TOP, GAME, BOT = 86, 470, 96                   # top band / play area / bottom (caption) band
H = TOP + GAME + BOT
M = 60                                          # inner margin of the play area
ALLY, ENEMY = (70, 200, 255), (255, 92, 76)


def load(framedir):
    out = []
    for f in sorted(glob.glob(os.path.join(framedir, "*.npy"))):
        fr = np.load(f)
        a = fr[fr[:, HP] > 0]
        if len(a) and np.any(np.isin(a[:, ALLI], [1, 4])):   # skip all-neutral post-game frames
            out.append(fr)
    return out


def bbox(frames):
    xs, ys = [], []
    for fr in frames:
        a = fr[fr[:, HP] > 0]
        a = a[np.isin(a[:, ALLI], [1, 4])]
        xs += list(a[:, X]); ys += list(a[:, Y])
    return (min(xs), max(xs), min(ys), max(ys)) if xs else (0, 1, 0, 1)


def font(sz, bold=True):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/" + ("arialbd.ttf" if bold else "arial.ttf"), sz)
    except Exception:
        return ImageFont.load_default()


def shape(d, x, y, r, col, square):
    box = [x - r, y - r, x + r, y + r]
    (d.rectangle if square else d.ellipse)(box, fill=col, outline=(245, 245, 245))


def main():
    fd, od = sys.argv[1], sys.argv[2]
    os.makedirs(od, exist_ok=True)
    frames = load(fd)
    if not frames:
        print("no frames in", fd); return
    x0, x1, y0, y1 = bbox(frames)
    span = max(x1 - x0, y1 - y0, 1.0)
    gw, gh = W - 2 * M, GAME - 2 * M
    S = min(gw, gh) / span                       # px per world unit (aspect-preserved, fits play area)
    ox = (gw - (x1 - x0) * S) / 2
    oy = (gh - (y1 - y0) * S) / 2

    def px(x, y):
        return M + ox + (x - x0) * S, TOP + M + oy + (y1 - y) * S   # north up

    f_t, f_l, f_h = font(17), font(13, False), font(20)
    for i, fr in enumerate(frames):
        img = Image.new("RGB", (W, H), (16, 20, 28))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, TOP], fill=(10, 13, 19))
        d.rectangle([0, H - BOT, W, H], fill=(10, 13, 19))
        d.text((14, 9), "StarCraft II  -  3s5z  -  top-down tactical view", font=f_t, fill=(228, 228, 228))
        # legend
        shape(d, 24, 48, 7, (185, 185, 185), False); d.text((38, 41), "Stalker (ranged)", font=f_l, fill=(205, 205, 205))
        shape(d, 24, 70, 7, (185, 185, 185), True);  d.text((38, 63), "Zealot (melee)",  font=f_l, fill=(205, 205, 205))
        d.text((196, 41), "cyan = allied (LLM-controlled)", font=f_l, fill=ALLY)
        d.text((196, 63), "red = enemy", font=f_l, fill=ENEMY)
        na = ne = 0
        for u in fr[fr[:, HP] > 0]:
            al = int(u[ALLI])
            if al == 1: col, na = ALLY, na + 1
            elif al == 4: col, ne = ENEMY, ne + 1
            else: continue
            x, y = px(u[X], u[Y])
            r = max(6, min(16, 6 + float(u[HP]) / 11.0))
            shape(d, x, y, r, col, int(u[UT]) == ZEALOT)
        d.text((470, 12), f"Allied units: {na}", font=f_h, fill=ALLY)
        d.text((470, 40), f"Enemy units: {ne}", font=f_h, fill=ENEMY)
        img.save(os.path.join(od, f"{i:04d}.png"))
    print(f"rendered {len(frames)} frames -> {od}  bbox x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}]")


if __name__ == "__main__":
    main()
