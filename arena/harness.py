"""The streaming command loop.

For each command: render it, time the model's response, score grounding against
the ground truth, mark a deadline miss if the response missed the tick budget,
then tick the uncontrolled agents (the clock does not wait). This is the
synchronous form; a truly concurrent clock (the world advancing on its own thread
while the model thinks) is the next step — see TODO.
"""
from __future__ import annotations

import random
import time

from .commands import sample_command
from .metrics import Metrics
from .world import GridWorld


def run_session(client, *, grid: int, agents: int, npcs: int,
                tick_ms: int, n_commands: int, seed: int = 0,
                recorder=None) -> Metrics:
    rng = random.Random(seed)
    world = GridWorld.random_init(grid, agents, npcs, rng=rng)
    metrics = Metrics()

    for step in range(n_commands):
        command = sample_command(world, rng)
        before = world.snapshot() if recorder is not None else None

        t0 = time.perf_counter()
        action = client.act(world, command)              # the model (or mock)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        correct = action == command.ground_truth()
        missed = latency_ms > tick_ms
        metrics.record(correct, latency_ms, missed)

        # A late action is dropped, the way a late decision simply does not
        # happen under a real clock; an on-time one is applied.
        if not missed:
            world.apply(list(action))
        world.tick_npcs()                                # the clock advances regardless

        if recorder is not None:
            recorder.add(step, command.text, before, world.snapshot(),
                         correct, missed, latency_ms)

        # TODO: concurrent clock — tick the world on a timer thread during act(),
        #       so a slow response sees a changed world, not just a dropped action.
        # TODO: drive command rate explicitly (issue at a target rate, queue overruns).

    return metrics
