"""Single-server command-stream queueing model (arena.rate.simulate_stream).

Commands arrive at a target rate; one model serves them FIFO. A command's
response time is queue-wait + service (model latency); it misses if that exceeds
the deadline. With a bounded queue, overruns are dropped. All expected values
below are hand-computed.
"""
from arena.rate import simulate_stream


def test_no_queue_when_arrivals_slower_than_service():
    # service 100ms each; arrivals every 1000ms (1 Hz) -> each finishes before the next
    r = simulate_stream([100.0] * 5, rate_hz=1.0, deadline_ms=200.0)
    assert r.responses == [100.0] * 5
    assert r.missed == [False] * 5
    assert r.dropped == [False] * 5
    assert r.max_in_system == 1
    assert r.stable is True
    assert r.served == 5


def test_arrival_times_follow_rate():
    # 2 Hz -> one command every 500 ms, first at t=0
    r = simulate_stream([10.0] * 4, rate_hz=2.0, deadline_ms=1000.0)
    assert r.arrivals == [0.0, 500.0, 1000.0, 1500.0]


def test_backlog_builds_and_causes_misses():
    # service 100ms; arrivals every 50ms (20 Hz) -> backlog grows unbounded
    r = simulate_stream([100.0] * 6, rate_hz=20.0, deadline_ms=200.0)
    assert r.responses == [100.0, 150.0, 200.0, 250.0, 300.0, 350.0]
    # deadline 200: response > 200 misses -> last three
    assert r.missed == [False, False, False, True, True, True]
    assert r.stable is False


def test_bounded_queue_drops_overruns():
    # cap=2 in-system; service 100ms; arrivals every 50ms (20 Hz)
    r = simulate_stream([100.0] * 6, rate_hz=20.0, deadline_ms=10_000.0, queue_cap=2)
    assert r.dropped == [False, False, False, True, False, True]
    assert r.served == 4
    # served commands all meet the (huge) deadline
    assert r.missed == [False, False, False, False, False, False]
