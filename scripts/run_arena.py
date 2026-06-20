#!/usr/bin/env python
"""Run one command-arena session and print a metrics report.

    python scripts/run_arena.py --mock --commands 50           # offline, no GPU
    python scripts/run_arena.py --commands 200 --tick-ms 500   # against served model
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.config import load_config           # noqa: E402
from arena.harness import run_session          # noqa: E402
from arena.model_client import MockClient, RealClient   # noqa: E402


def main() -> None:
    cfg = load_config()
    p = argparse.ArgumentParser(description="Run a command-arena session.")
    p.add_argument("--mock", action="store_true", help="use the no-GPU mock model")
    p.add_argument("--commands", type=int, default=100)
    p.add_argument("--grid", type=int, default=cfg.grid)
    p.add_argument("--agents", type=int, default=cfg.agents)
    p.add_argument("--npcs", type=int, default=cfg.npcs)
    p.add_argument("--tick-ms", type=int, default=cfg.tick_ms)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--save", type=str, default="", help="write the report JSON here")
    args = p.parse_args()

    if args.mock:
        client = MockClient()
        print("[mock model — validating the harness, not a real result]")
    else:
        client = RealClient(cfg.base_url, cfg.api_key, cfg.model)
        print(f"[model {cfg.model} @ {cfg.base_url}]")

    metrics = run_session(
        client, grid=args.grid, agents=args.agents, npcs=args.npcs,
        tick_ms=args.tick_ms, n_commands=args.commands, seed=args.seed,
    )
    report = metrics.report()
    print(json.dumps(report, indent=2))
    if args.save:
        Path(args.save).write_text(json.dumps(report, indent=2))
        print(f"saved -> {args.save}")


if __name__ == "__main__":
    main()
