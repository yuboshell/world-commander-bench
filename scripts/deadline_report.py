#!/usr/bin/env python
"""Print real-time deadline accounting for a metrics log (arena or SC2).

    python scripts/deadline_report.py outputs/sc2_2s3z_4B.jsonl
    python scripts/deadline_report.py outputs/sc2_2s3z_4B.jsonl --deadlines 500,2000,5000

Reads a JSONL where each line has a "latency_ms" field and reports, per deadline,
how many decisions land on time vs are dropped (late), plus the synchronous
decision throughput (decisions/sec). Pure post-hoc — no model calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.metrics import deadline_report     # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("path", help="JSONL metrics file with latency_ms per line")
    p.add_argument("--deadlines", default="500,1000,2000,5000,8000",
                   help="comma-separated deadline budgets in ms")
    args = p.parse_args()

    lats = [json.loads(l)["latency_ms"] for l in open(args.path) if l.strip()]
    if not lats:
        print("no samples")
        return
    deadlines = [int(x) for x in args.deadlines.split(",")]
    print(f"{args.path}: {len(lats)} decisions, "
          f"synchronous throughput {deadline_report(lats, 0)['throughput_hz']:.3f} dec/s\n")
    print(f"{'deadline':>9} | {'on-time':>7} | {'dropped':>7} | {'miss rate':>9}")
    print("-" * 42)
    for d in deadlines:
        r = deadline_report(lats, d)
        print(f"{d:>6} ms | {r['on_time']:>7} | {r['missed']:>7} | {r['miss_rate']:>9.2f}")


if __name__ == "__main__":
    main()
