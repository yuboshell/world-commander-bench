#!/usr/bin/env python
"""Representation A/B: does an intuitive coordinate framing lift macro grounding?

    python scripts/representation_sweep.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ --tag 4B

Same macro commands + model, two world-render styles:
  xy  — raw coords, "N decreases y" (origin top-left)   [the current baseline]
  map — (column, height), north = up = larger height     [intuitive]
Only the numbers shown change; N/S/E/W keep their meaning, so this isolates whether
the coordinate convention confounds spatial reasoning (macro per-agent grounding
was *below* a random-valid baseline under xy). The world evolves deterministically
(apply each command's canonical answer + tick NPCs), so both styles see an identical
command stream — the only variable is the prompt framing. Writes outputs/representation_<tag>.json.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import MACRO_FORMS, sample_command    # noqa: E402
from arena.config import load_config                      # noqa: E402
from arena.model_client import RealClient                 # noqa: E402
from arena.world import GridWorld                          # noqa: E402


def _pct(xs, q):
    xs = sorted(xs)
    return xs[max(0, math.ceil(q / 100 * len(xs)) - 1)] if xs else 0.0


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=cfg.base_url)
    ap.add_argument("--model", default=cfg.model)
    ap.add_argument("--commands", type=int, default=60)
    ap.add_argument("--tick-ms", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="model")
    ap.add_argument("--styles", default="xy,map")
    ap.add_argument("--fresh", action="store_true",
                    help="fresh random world per command (unbiased states, no trajectory entanglement)")
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()

    rows = []
    for style in a.styles.split(","):
        client = RealClient(a.base_url, cfg.api_key, a.model, schema="json", render_style=style)
        cmd_rng = random.Random(a.seed)                    # identical command stream per style
        world = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs,
                                      rng=random.Random(a.seed + 1))
        ca = ta = cmd_ok = 0
        lats = []
        for i in range(a.commands):
            if a.fresh:  # independent state per command, identical across styles
                world = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs,
                                              rng=random.Random(a.seed + 1000 + i))
                cmd = sample_command(world, random.Random(a.seed + 5000 + i), forms=MACRO_FORMS)
            else:
                cmd = sample_command(world, cmd_rng, forms=MACRO_FORMS)
            t0 = time.perf_counter()
            action = client.act(world, cmd)
            lats.append((time.perf_counter() - t0) * 1000.0)
            c, t = cmd.agent_grounding(action)
            ca += c
            ta += t
            cmd_ok += int(cmd.is_correct(action))
            if not a.fresh:
                world.apply(list(cmd.ground_truth()))      # deterministic evolution (style-independent)
                world.tick_npcs()
        row = {"style": style, "n": a.commands,
               "grounding_per_agent": round(ca / max(1, ta), 3),
               "grounding_per_command": round(cmd_ok / a.commands, 3),
               "lat_p50": round(_pct(lats, 50), 1), "lat_p95": round(_pct(lats, 95), 1)}
        rows.append(row)
        print(a.tag, row)

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    out = Path(a.outdir) / f"representation_{a.tag}.json"
    json.dump({"model": a.model, "tag": a.tag, "commands": a.commands, "rows": rows},
              open(out, "w"), indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
