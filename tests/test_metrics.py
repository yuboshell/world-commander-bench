"""Tests for metric helpers."""
from arena.metrics import deadline_report, miss_rate


def test_miss_rate_is_a_threshold_on_latency():
    lats = [100.0, 400.0, 600.0, 1000.0]
    assert miss_rate(lats, 500) == 0.5      # 600 and 1000 exceed 500
    assert miss_rate(lats, 1000) == 0.0     # strict >, so 1000 is on time
    assert miss_rate(lats, 0) == 1.0
    assert miss_rate([], 500) == 0.0        # empty -> no misses


def test_deadline_report_counts_drops_and_throughput():
    lats = [100.0, 400.0, 600.0, 1000.0]
    r = deadline_report(lats, 500)
    assert r["n"] == 4
    assert r["missed"] == 2 and r["on_time"] == 2     # 600, 1000 exceed 500
    assert r["miss_rate"] == 0.5
    assert r["mean_ms"] == 525.0
    # synchronous throughput: decisions per real second = 1000 / mean latency
    assert round(r["throughput_hz"], 3) == round(1000.0 / 525.0, 3)


def test_deadline_report_empty():
    r = deadline_report([], 500)
    assert r["n"] == 0 and r["miss_rate"] == 0.0 and r["throughput_hz"] == 0.0
