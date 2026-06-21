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

import math
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


def simulate_arrivals(latencies_ms, arrivals_ms, deadline_ms: float,
                      queue_cap: int | None = None) -> StreamResult:
    """Single-server FIFO queue over **explicit** (non-decreasing) arrival times.
    Command i arrives at arrivals_ms[i]; it starts when it has arrived and the
    server is free, finishes after its latency, and misses if (finish - arrival)
    > deadline_ms. With `queue_cap`, a command arriving when `queue_cap` are already
    in the system is dropped. This backs both the steady-rate and burst loads."""
    latencies_ms = list(latencies_ms)
    arrivals_ms = list(arrivals_ms)
    n = len(latencies_ms)

    responses: list[float | None] = [None] * n
    missed = [False] * n
    dropped = [False] * n

    last_finish = 0.0          # finish time of the last *served* command
    in_system: deque[float] = deque()   # finish times of accepted, not-yet-done commands
    max_in_system = 0

    for i in range(n):
        a = arrivals_ms[i]
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
    gaps = [arrivals_ms[i] - arrivals_ms[i - 1] for i in range(1, n)]
    mean_gap = sum(gaps) / len(gaps) if gaps else float("inf")
    stable = mean_service == 0.0 or mean_gap > mean_service
    return StreamResult(arrivals_ms, responses, missed, dropped, max_in_system, stable)


def simulate_stream(latencies_ms, rate_hz: float, deadline_ms: float,
                    queue_cap: int | None = None) -> StreamResult:
    """Replay `latencies_ms` arriving at a steady `rate_hz` (command i at
    i*(1000/rate_hz) ms). Thin wrapper over `simulate_arrivals`."""
    if rate_hz <= 0:
        raise ValueError("rate_hz must be positive")
    latencies_ms = list(latencies_ms)
    interarrival = 1000.0 / rate_hz
    arrivals = [i * interarrival for i in range(len(latencies_ms))]
    return simulate_arrivals(latencies_ms, arrivals, deadline_ms, queue_cap)


def burst_arrivals(n_bursts: int, burst_size: int, gap_ms: float,
                   intra_ms: float = 0.0) -> list[float]:
    """Arrival schedule for `n_bursts` bursts of `burst_size` commands, `intra_ms`
    apart within a burst, with `gap_ms` idle between bursts — the realistic
    crisis-flurry load (a human firing several commands at once, then a lull),
    rather than a steady rate. Feed to `simulate_arrivals`."""
    arrivals: list[float] = []
    t = 0.0
    for _ in range(n_bursts):
        for k in range(burst_size):
            arrivals.append(t + k * intra_ms)
        t += (burst_size - 1) * intra_ms + gap_ms
    return arrivals


def _percentile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = max(0, math.ceil(q / 100.0 * len(s)) - 1)
    return s[idx]


def load_curve(latencies_ms, rates_hz, deadline_ms: float,
               queue_cap: int | None = None) -> list[dict]:
    """Replay `latencies_ms` at each rate in `rates_hz`; return one summary row
    per rate. `unmet_rate` = commands that produced no on-time action (late OR
    dropped) — the headline load metric."""
    latencies_ms = list(latencies_ms)
    n = len(latencies_ms) or 1
    rows = []
    for rate in rates_hz:
        r = simulate_stream(latencies_ms, rate, deadline_ms, queue_cap)
        n_miss = sum(r.missed)
        n_drop = sum(r.dropped)
        served_resp = [x for x in r.responses if x is not None]
        rows.append({
            "rate_hz": rate,
            "miss_rate": n_miss / n,
            "drop_rate": n_drop / n,
            "unmet_rate": (n_miss + n_drop) / n,
            "served": r.served,
            "max_in_system": r.max_in_system,
            "stable": r.stable,
            "p95_response_ms": _percentile(served_resp, 95),
        })
    return rows
