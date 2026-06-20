"""Command-stream queueing model.

The arena's real test is the *stream*: commands arrive at some rate while a
single model serves them one at a time. If commands arrive faster than the model
answers, they queue — and a command's deadline is measured from when it *arrived*,
not when the model got to it. So the interesting metric is the deadline-miss rate
as a function of arrival rate (a load curve), which this computes analytically
from a recorded sequence of per-command model latencies.

`simulate_stream` runs a single-server FIFO queue: measure each command's model
latency once, then replay the stream at any target rate (cheap) instead of re-
running the model per rate. With `queue_cap` set, arrivals that would exceed the
in-system bound are dropped (overrun) rather than queued unboundedly.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class StreamResult:
    arrivals: list[float]              # ms, command i issued at i / rate
    responses: list[float | None]     # ms from arrival to action applied; None if dropped
    missed: list[bool]                # served but response > deadline
    dropped: list[bool]               # rejected because the queue was full
    max_in_system: int                # peak backlog (queue + in service)
    stable: bool                      # arrival interval > mean service (queue won't run away)

    @property
    def n(self) -> int:
        return len(self.arrivals)

    @property
    def served(self) -> int:
        return sum(1 for d in self.dropped if not d)


def simulate_stream(latencies_ms, rate_hz: float, deadline_ms: float,
                    queue_cap: int | None = None) -> StreamResult:
    """Replay `latencies_ms` as a command stream arriving at `rate_hz`.

    Single FIFO server. Command i arrives at i * (1000 / rate_hz) ms; it starts
    when both it has arrived and the server is free, finishes after its latency,
    and misses if (finish - arrival) > deadline_ms. With `queue_cap`, a command
    arriving when `queue_cap` commands are already in the system is dropped.
    """
    if rate_hz <= 0:
        raise ValueError("rate_hz must be positive")
    latencies_ms = list(latencies_ms)
    n = len(latencies_ms)
    interarrival = 1000.0 / rate_hz
    arrivals = [i * interarrival for i in range(n)]

    responses: list[float | None] = [None] * n
    missed = [False] * n
    dropped = [False] * n

    last_finish = 0.0          # finish time of the last *served* command
    in_system: deque[float] = deque()   # finish times of accepted, not-yet-done commands
    max_in_system = 0

    for i in range(n):
        a = arrivals[i]
        while in_system and in_system[0] <= a:   # drop those completed by now
            in_system.popleft()
        if queue_cap is not None and len(in_system) >= queue_cap:
            dropped[i] = True
            continue
        start = max(a, last_finish)
        finish = start + latencies_ms[i]
        responses[i] = finish - a
        missed[i] = responses[i] > deadline_ms
        last_finish = finish
        in_system.append(finish)
        max_in_system = max(max_in_system, len(in_system))

    mean_service = sum(latencies_ms) / n if n else 0.0
    stable = mean_service == 0.0 or interarrival > mean_service
    return StreamResult(arrivals, responses, missed, dropped, max_in_system, stable)
