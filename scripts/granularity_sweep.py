#!/usr/bin/env python
"""Macro vs micro: same model, two command pools, compare grounding + latency.

    python scripts/granularity_sweep.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ

Micro = explicit reference ("move the red agent north"); macro = state-dependent
goal ("everyone move toward the center"). Macro should cost more output (per-agent
directions) and lower grounding (spatial reasoning, not name lookup) — the new
(granularity × deadline) axis. Writes outputs/granularity.json.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import MACRO_FORMS, MICRO_FORMS       # noqa: E402
from arena.config import load_config                      # noqa: E402
from arena.harness import run_session                     # noqa: E402
from arena.model_client import RealClient                 # noqa: E402
from arena.recorder import Recorder                       # noqa: E402


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
        rec = Recorder()
        m = run_session(client, grid=cfg.grid, agents=cfg.agents, npcs=cfg.npcs,
                        tick_ms=a.tick_ms, n_commands=a.commands, seed=a.seed,
                        recorder=rec, command_forms=forms)
        lat = [f.latency_ms for f in rec.frames]
        rep = m.report()
        row = {"granularity": gran, "grounding": rep["grounding_accuracy"], "n": len(lat),
               "lat_mean": round(statistics.mean(lat), 1), "lat_p50": round(_pct(lat, 50), 1),
               "lat_p95": round(_pct(lat, 95), 1),
               "miss@500": round(sum(l > 500 for l in lat) / len(lat), 3),
               "miss@1000": round(sum(l > 1000 for l in lat) / len(lat), 3)}
        rows.append(row)
        print(gran, row)

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    out = Path(a.outdir) / "granularity.json"
    json.dump({"model": a.model, "commands": a.commands, "tick_ms": a.tick_ms, "rows": rows},
              open(out, "w"), indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
