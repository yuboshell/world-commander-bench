#!/usr/bin/env python
"""Run the E3 button-desk (L0) and produce a success-vs-window frontier.

    python scripts/run_desk.py --mock --rounds 100                 # offline smoke
    python scripts/run_desk.py --base-url http://127.0.0.1:8001/v1 --model Qwen/Qwen3-4B-AWQ --rounds 100

Each round: a random button lights; the command refers to it (direct/colour/spatial);
the executor grounds it (timed); the hand reaches it (distance/speed). Success =
grounded AND parse+ground latency + reach time <= window W. Sweeps W → frontier, the
E3 analog of the arena's deadline frontier (now with a physical-execution term).
Writes outputs/desk.json.
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

from desk.commander import LLMCommander, MockCommander  # noqa: E402
from desk.eval import success_curve                # noqa: E402
from desk.executor import MockDeskExecutor, RealDeskExecutor  # noqa: E402
from desk.world import DeskWorld                    # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--api-key", default="EMPTY")
    ap.add_argument("--rounds", type=int, default=100)
    ap.add_argument("--n-buttons", type=int, default=2)
    ap.add_argument("--speed", type=float, default=1.0, help="desk-units/sec (hand speed)")
    ap.add_argument("--rest-x", type=float, default=0.0, help="hand rest/home position")
    ap.add_argument("--carryover", action="store_true",
                    help="hand stays where it last pressed (default: return to rest each round)")
    ap.add_argument("--llm-commander", action="store_true",
                    help="use an LLM as the commander (human stand-in); default scripted")
    ap.add_argument("--windows", default="300,500,800,1200,2000,3000", help="lit windows (ms)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="outputs")
    a = ap.parse_args()
    windows = [float(x) for x in a.windows.split(",")]

    rng = random.Random(a.seed)
    world = DeskWorld.make(n=a.n_buttons, speed=a.speed, rest_x=a.rest_x)
    executor = (MockDeskExecutor(rng=random.Random(a.seed + 1)) if a.mock
                else RealDeskExecutor(a.base_url, a.api_key, a.model))
    commander = (LLMCommander(a.base_url, a.api_key, a.model) if a.llm_commander
                 else MockCommander())

    rounds = []          # (grounded, executor_ms, reach_ms)
    commander_ms = []
    grounded_n = 0
    for _ in range(a.rounds):
        if not a.carryover:
            world.reset_hand()       # hands relax to rest between rounds
        k = rng.randrange(a.n_buttons)
        world.lit = k
        tc = time.perf_counter()
        cmd = commander.command(world, rng)            # commander (human stand-in) reasons
        commander_ms.append((time.perf_counter() - tc) * 1000.0)
        t0 = time.perf_counter()
        action = executor.act(world, cmd)              # executor parses + grounds (the focus)
        lat = (time.perf_counter() - t0) * 1000.0
        grounded = cmd.is_correct(action)
        grounded_n += int(grounded)
        reach = world.reach_ms(k)
        rounds.append((grounded, lat, reach))          # deadline budget = executor + reach
        if action:
            world.press(next(iter(action)))   # hand carries over to where it pressed
        world.lit = None

    lats = [p for _, p, _ in rounds]
    reaches = [r for _, _, r in rounds]
    res = {"model": "mock" if a.mock else a.model, "rounds": a.rounds,
           "n_buttons": a.n_buttons, "speed": a.speed,
           "commander": ("scripted (stand-in)" if not a.llm_commander
                         else f"LLM stand-in ({a.model})"),
           "commander_p50_ms": round(statistics.median(commander_ms), 1),
           "grounding_accuracy": round(grounded_n / a.rounds, 3),
           "parse_ground_p50_ms": round(statistics.median(lats), 1),
           "reach_p50_ms": round(statistics.median(reaches), 1),
           "frontier": [{"window_ms": c["window_ms"], "success_rate": round(c["success_rate"], 3)}
                        for c in success_curve(rounds, windows)]}
    print(f"commander {res['commander']} p50 {res['commander_p50_ms']} ms | "
          f"grounding {res['grounding_accuracy']} | executor(parse+ground) p50 "
          f"{res['parse_ground_p50_ms']} ms | reach p50 {res['reach_p50_ms']} ms")
    for c in res["frontier"]:
        print(f"  W={c['window_ms']:.0f} ms -> success {c['success_rate']}")
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    json.dump(res, open(Path(a.outdir) / "desk.json", "w"), indent=2)
    print("wrote", Path(a.outdir) / "desk.json")


if __name__ == "__main__":
    main()
