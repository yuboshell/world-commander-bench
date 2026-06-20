"""Tests for metric helpers."""
from arena.metrics import miss_rate


def test_miss_rate_is_a_threshold_on_latency():
    lats = [100.0, 400.0, 600.0, 1000.0]
    assert miss_rate(lats, 500) == 0.5      # 600 and 1000 exceed 500
    assert miss_rate(lats, 1000) == 0.0     # strict >, so 1000 is on time
    assert miss_rate(lats, 0) == 1.0
    assert miss_rate([], 500) == 0.0        # empty -> no misses
