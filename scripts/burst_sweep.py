#!/usr/bin/env python
"""Burst-load: can a model clear a crisis flurry before the consequence deadline?

    python scripts/burst_sweep.py --deadline-ms 2000

The realistic stress isn't a steady command rate — it's a **burst** ("stop! turn!
retreat!") arriving near-simultaneously, then a lull. Replays each model's recorded
per-command latencies (outputs/model_*.json, no GPU) through bursts of increasing
size (all arriving at once) and reports the share of the burst that still produces an
on-time action at the deadline. A fast model clears a bigger burst in time.
Writes outputs/burst_sweep.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.rate import burst_arrivals, simulate_arrivals   # noqa: E402

SIZE = {"0.6B": 0.6, "1.7B": 1.7, "4B": 4, "8B": 8, "14B": 14}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="outputs")
    ap.add_argument("--outdir", default="outputs")
    ap.add_argument("--deadline-ms", type=float, default=2000.0)
    ap.add_argument("--sizes", default="1,2,3,5,8", help="burst sizes (simultaneous)")
    a = ap.parse_args()
    burst_sizes = [int(x) for x in a.sizes.split(",")]

    models = []
    for f in sorted(glob.glob(str(Path(a.indir) / "model_*.json"))):
        d = json.load(open(f))
        lat = [r["lat"] for r in d.get("rows", []) if "lat" in r]
        if lat:
            models.append((SIZE.get(d.get("label", ""), 99), d["label"], lat))
    if not models:
        sys.exit("no model_*.json with latencies found")

    rows = []
    for _, label, lat in sorted(models):
        served = {}
        for k in burst_sizes:
            lats_k = [lat[i % len(lat)] for i in range(k)]      # k commands arrive at once
            r = simulate_arrivals(lats_k, burst_arrivals(1, k, gap_ms=0), a.deadline_ms)
            on_time = sum(1 for i, resp in enumerate(r.responses)
                          if resp is not None and not r.missed[i])
            served[k] = round(on_time / k, 3)
        rows.append({"model": label, "on_time_fraction_by_burst": served})
        print(f"{label:>6}  " + "  ".join(f"burst{k}={served[k]:.2f}" for k in burst_sizes))

    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    out = Path(a.outdir) / "burst_sweep.json"
    json.dump({"deadline_ms": a.deadline_ms, "burst_sizes": burst_sizes, "models": rows},
              open(out, "w"), indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
