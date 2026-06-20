"""Tests for the concurrent clock — the world advances in real time, on its own
thread, while the model thinks. Timing assertions use wide tolerances."""
import time

from arena.clock import ConcurrentClock
from arena.harness import run_session
from arena.recorder import Recorder
from arena.world import GridWorld


def test_clock_ticks_in_real_time():
    world = GridWorld.random_init(8, 4, 4)
    clock = ConcurrentClock(world, tick_ms=10)
    clock.start()
    time.sleep(0.12)            # ~12 ticks expected
    clock.stop()
    assert clock.ticks >= 4, f"clock should tick several times, got {clock.ticks}"


def test_clock_advances_npcs():
    world = GridWorld.random_init(8, 4, 4)
    before = [(a.name, a.x, a.y) for a in world.agents if not a.controlled]
    clock = ConcurrentClock(world, tick_ms=5)
    clock.start()
    time.sleep(0.1)             # ~20 ticks of random walk
    clock.stop()
    after = [(a.name, a.x, a.y) for a in world.agents if not a.controlled]
    assert clock.ticks > 0
    assert before != after, "NPCs should have moved while the clock ran"


class _SlowClient:
    """A model that takes a fixed wall-clock time to 'think', always correct."""
    def act(self, world, command):
        time.sleep(0.03)
        return command.ground_truth()


def test_world_advances_while_the_model_thinks():
    rec = Recorder()
    run_session(_SlowClient(), grid=8, agents=4, npcs=4, tick_ms=5,
                n_commands=3, seed=0, recorder=rec, concurrent=True)
    npc_first = [(n, x, y) for (n, x, y, c) in rec.frames[0].before if not c]
    npc_last = [(n, x, y) for (n, x, y, c) in rec.frames[-1].after if not c]
    assert npc_first != npc_last, "the clock should have moved NPCs during thinking"


def test_synchronous_mode_still_runs():
    # concurrent=False: deterministic, one NPC tick per command, no threads.
    m = run_session(_SlowClient(), grid=8, agents=4, npcs=4, tick_ms=5,
                    n_commands=2, seed=0, concurrent=False)
    assert m.report()["commands"] == 2
