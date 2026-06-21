"""The streaming command loop.

For each command: render it, time the model's response, score grounding against
the ground truth, mark a deadline miss if the response missed the tick budget,
and apply an on-time action. The clock does not wait: by default a concurrent
clock advances the uncontrolled agents on its own thread *during* the model's
think, so a slow response sees (and concedes to) a changed world, not just a
dropped action. Pass concurrent=False for the older, deterministic one-tick-per-
command behaviour (no threads).
"""
from __future__ import annotations

import random
import time

from .clock import ConcurrentClock
from .commands import sample_command
from .metrics import Metrics
from .world import GridWorld


def run_session(client, *, grid: int, agents: int, npcs: int,
                tick_ms: int, n_commands: int, seed: int = 0,
                recorder=None, concurrent: bool = True,
                command_forms: list[str] | None = None) -> Metrics:
    cmd_rng = random.Random(seed)        # command stream (main thread)
    npc_rng = random.Random(seed + 1)    # NPC moves (clock thread) — never shared
    world = GridWorld.random_init(grid, agents, npcs, rng=npc_rng)
    metrics = Metrics()

    clock = ConcurrentClock(world, tick_ms).start() if concurrent else None
    try:
        for step in range(n_commands):
            command = sample_command(world, cmd_rng, forms=command_forms)
            before = world.snapshot() if recorder is not None else None

            t0 = time.perf_counter()
            action = client.act(world, command)          # the model (or mock)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            correct = command.is_correct(action)
            missed = latency_ms > tick_ms
            metrics.record(correct, latency_ms, missed)

            # A late action is dropped, the way a late decision simply does not
            # happen under a real clock; an on-time one is applied.
            if not missed:
                world.apply(list(action))
            if clock is None:
                world.tick_npcs()                        # synchronous fallback: one tick

            if recorder is not None:
                recorder.add(step, command.text, command.targets, before,
                             world.snapshot(), correct, missed, latency_ms)
    finally:
        if clock is not None:
            clock.stop()

    # TODO: drive command rate explicitly (issue at a target rate, queue overruns).
    return metrics
