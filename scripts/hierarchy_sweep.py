#!/usr/bin/env python
"""Hierarchy experiment: does routing micro→small / macro→large beat either model alone?

    python scripts/hierarchy_sweep.py --small-url http://127.0.0.1:8001/v1 --small-model Qwen/Qwen3-4B-AWQ \
                                      --large-url http://127.0.0.1:8000/v1 --large-model Qwen/Qwen3-14B-AWQ

Motivated by the macro-capability curve: micro is solved cheaply by a small model,
macro needs the big (slow) one. A router that sends each command to the right model
should get ~large-grounding at well-below-large latency. We compare three policies
over one fixed stream (half micro, half macro; fresh state per command, identical
across policies): small-only, large-only, router. Writes outputs/hierarchy.json.
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

from arena.commands import MACRO_FORMS, MICRO_FORMS, sample_command   # noqa: E402
from arena.config import load_config                                  # noqa: E402
from arena.model_client import RealClient, RouterClient               # noqa: E402
from arena.world import GridWorld                                      # noqa: E402


def _p50(xs):
    return round(statistics.median(xs), 1) if xs else 0.0


def _grounding(rows, gran=None):
    sel = [r for r in rows if gran is None or r["gran"] == gran]
    tot = sum(r["t"] for r in sel)
    return round(sum(r["c"] for r in sel) / tot, 3) if tot else 0.0


def run_condition(client, pairs):
    rows = []
    for w, cmd in pairs:
        t0 = time.perf_counter()
        action = client.act(w, cmd)
        lat = (time.perf_counter() - t0) * 1000.0
        c, t = cmd.agent_grounding(action)
        rows.append({"gran": cmd.granularity, "c": c, "t": t, "lat": lat})
    return rows


def summary(name, rows):
    lats = [r["lat"] for r in rows]
    micro = [r["lat"] for r in rows if r["gran"] == "micro"]
    macro = [r["lat"] for r in rows if r["gran"] == "macro"]
    return {"policy": name, "n": len(rows),
            "grounding": _grounding(rows), "p50_lat": _p50(lats),
            "micro_grounding": _grounding(rows, "micro"), "micro_p50": _p50(micro),
            "macro_grounding": _grounding(rows, "macro"), "macro_p50": _p50(macro)}


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--small-url", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--small-model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--large-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--large-model", default="Qwen/Qwen3-14B-AWQ")
    ap.add_argument("--commands", type=int, default=80)
    ap.add_argument("--micro-frac", type=float, default=0.5, help="fraction of micro commands")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()

    # fixed stream: micro/macro mix per --micro-frac, fresh state per command, read-only
    pairs = []
    for i in range(a.commands):
        is_micro = random.Random(a.seed + 9000 + i).random() < a.micro_frac
        forms = MICRO_FORMS if is_micro else MACRO_FORMS
        w = GridWorld.random_init(cfg.grid, cfg.agents, cfg.npcs,
                                  rng=random.Random(a.seed + 1000 + i))
        cmd = sample_command(w, random.Random(a.seed + 5000 + i), forms=forms)
        pairs.append((w, cmd))

    small = RealClient(a.small_url, cfg.api_key, a.small_model, schema="json")
    large = RealClient(a.large_url, cfg.api_key, a.large_model, schema="json")
    router = RouterClient(small, large)

    out = []
    for name, client in (("small-only", small), ("large-only", large), ("router", router)):
        s = summary(name, run_condition(client, pairs))
        out.append(s)
        print(s)

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    res = {"small_model": a.small_model, "large_model": a.large_model,
           "commands": a.commands, "policies": out}
    json.dump(res, open(Path(a.outdir) / "hierarchy.json", "w"), indent=2)
    print("wrote", Path(a.outdir) / "hierarchy.json")


if __name__ == "__main__":
    main()
