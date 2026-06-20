"""The concurrent clock: the world advances in real time on its own thread.

The whole point of the arena is a clock that does not pause for the model. This
runs a background thread that ticks the uncontrolled agents every `tick_ms` of
wall-clock time, so a slow response sees (and concedes to) a changed world rather
than merely having its action dropped. The world is made thread-safe (see
GridWorld's lock); NPCs use a separate RNG from command sampling so the two
threads never share random state.
"""
from __future__ import annotations

import threading
import time


class ConcurrentClock:
    def __init__(self, world, tick_ms: int):
        self.world = world
        self.interval = tick_ms / 1000.0
        self.ticks = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        next_t = time.perf_counter() + self.interval
        while not self._stop.is_set():
            now = time.perf_counter()
            if now >= next_t:
                self.world.tick_npcs()
                self.ticks += 1
                next_t += self.interval
            else:
                # wait until the next tick (or until stopped), whichever first
                self._stop.wait(min(self.interval, next_t - now))

    def start(self) -> "ConcurrentClock":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
