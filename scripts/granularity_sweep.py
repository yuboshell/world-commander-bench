#!/usr/bin/env python
"""Macro vs micro: same model, two command pools, compare grounding + latency.

    python scripts/granularity_sweep.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ

Micro = explicit reference ("move the red agent north"); macro = state-dependent
goal ("everyone move toward the center"). Reports BOTH a strict per-command score
(all commanded agents correct) and the fairer **per-agent** acceptable-set score
(fraction of movable agents sent in a progress-making direction) — macro commands
move several agents at once, so per-command all-or-nothing badly under-counts.
Writes outputs/granularity.json.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import MACRO_FORMS, MICRO_FORMS, sample_command   # noqa: E402
from arena.config import load_config                                  # noqa: E402
from arena.model_client import RealClient                             # noqa: E402
from arena.world import GridWorld                                     # noqa: E402
import random                                                         # noqa: E402


def _pct(xs, q):
    xs = sorted(xs)
    return xs[max(0, math.ceil(q / 100 * len(xs)) - 1)] if xs else 0.0


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=cfg.base_url)
    ap.add_argument("--model", default=cfg.model)
    ap.add_argument("--commands", type=int, default=80)
    ap.add_argument("--tick-ms", type=int, default=1000)   # human-paced deadline
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()

    rows = []
    for gran, forms in (("micro", MICRO_FORMS), ("macro", MACRO_FORMS)):
        client = RealClient(a.base_url, cfg.api_key, a.model, schema="json")
        cmd_rng = random.Random(a.seed)
        world = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs,
                                      rng=random.Random(a.seed + 1))
        ca = ta = cmd_ok = 0
        lats = []
        for _ in range(a.commands):
            cmd = sample_command(world, cmd_rng, forms=forms)
            t0 = time.perf_counter()
            action = client.act(world, cmd)
            lats.append((time.perf_counter() - t0) * 1000.0)
            c, t = cmd.agent_grounding(action)
            ca += c
            ta += t
            cmd_ok += int(cmd.is_correct(action))
            if lats[-1] <= a.tick_ms:
                world.apply(list(action))
            world.tick_npcs()
        row = {"granularity": gran, "n": a.commands,
               "grounding_per_agent": round(ca / max(1, ta), 3),
               "grounding_per_command": round(cmd_ok / a.commands, 3),
               "lat_mean": round(statistics.mean(lats), 1),
               "lat_p50": round(_pct(lats, 50), 1), "lat_p95": round(_pct(lats, 95), 1),
               "miss@500": round(sum(l > 500 for l in lats) / a.commands, 3),
               "miss@1000": round(sum(l > 1000 for l in lats) / a.commands, 3)}
        rows.append(row)
        print(gran, row)

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    out = Path(a.outdir) / "granularity.json"
    json.dump({"model": a.model, "commands": a.commands, "tick_ms": a.tick_ms, "rows": rows},
              open(out, "w"), indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
