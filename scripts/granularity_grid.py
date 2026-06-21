#!/usr/bin/env python
"""Grounding by command granularity: micro (named) vs region (spatial reference) vs
macro (goal planning), on fresh random states. Places region on the difficulty
spectrum between named-micro and goal-macro.

    python scripts/granularity_grid.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import (MACRO_FORMS, MICRO_FORMS, REGION_FORMS,   # noqa: E402
                            sample_command)
from arena.config import load_config                                  # noqa: E402
from arena.model_client import RealClient                             # noqa: E402
from arena.world import GridWorld                                     # noqa: E402

POOLS = {"micro": MICRO_FORMS, "region": REGION_FORMS, "macro": MACRO_FORMS}


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--commands", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()

    client = RealClient(a.base_url, cfg.api_key, a.model, schema="json")
    rows = []
    for gran, pool in POOLS.items():
        ca = ta = 0
        lats = []
        for i in range(a.commands):
            w = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs,
                                      rng=random.Random(a.seed + 1000 + i))
            cmd = sample_command(w, random.Random(a.seed + 5000 + i), forms=pool)
            t0 = time.perf_counter()
            action = client.act(w, cmd)
            lats.append((time.perf_counter() - t0) * 1000.0)
            c, t = cmd.agent_grounding(action)
            ca += c
            ta += t
        row = {"granularity": gran, "grounding_per_agent": round(ca / max(1, ta), 3),
               "lat_p50": round(statistics.median(lats), 1)}
        rows.append(row)
        print(row)

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    json.dump({"model": a.model, "commands": a.commands, "rows": rows},
              open(Path(a.outdir) / "granularity_grid.json", "w"), indent=2)
    print("wrote", Path(a.outdir) / "granularity_grid.json")


if __name__ == "__main__":
    main()
