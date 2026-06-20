#!/usr/bin/env python
"""Run the arena against one OpenAI-compatible endpoint and dump compact rows.

Used by the model-size sweep: each served model is run separately (one fits on
GPU 2 at a time), and the per-command rows are saved so the overlay can be built
afterwards without keeping every model resident.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.harness import run_session          # noqa: E402
from arena.model_client import RealClient       # noqa: E402
from arena.recorder import Recorder            # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--schema", default="json")
    p.add_argument("--commands", type=int, default=90)
    p.add_argument("--tick-ms", type=int, default=500)
    p.add_argument("--grid", type=int, default=8)
    p.add_argument("--agents", type=int, default=4)
    p.add_argument("--npcs", type=int, default=4)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    client = RealClient(a.base_url, "EMPTY", a.model, schema=a.schema)
    rec = Recorder()
    m = run_session(client, grid=a.grid, agents=a.agents, npcs=a.npcs,
                    tick_ms=a.tick_ms, n_commands=a.commands, seed=a.seed,
                    recorder=rec)
    rows = [{"lat": f.latency_ms, "nt": len(f.targets),
             "correct": f.correct, "missed": f.missed} for f in rec.frames]
    Path(a.out).write_text(json.dumps(
        {"label": a.label, "model": a.model, "report": m.report(), "rows": rows}))
    print(f"[{a.label}] {m.report()}")


if __name__ == "__main__":
    main()
