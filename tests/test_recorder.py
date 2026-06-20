"""Tests for the per-tick state recorder used by visualization."""
import random

from arena.harness import run_session
from arena.model_client import MockClient
from arena.recorder import Recorder


def test_recorder_captures_one_frame_per_command():
    rec = Recorder()
    run_session(
        MockClient(accuracy=1.0, rng=random.Random(0)),
        grid=8, agents=4, npcs=4, tick_ms=10_000, n_commands=5, seed=0,
        recorder=rec,
    )
    assert len(rec.frames) == 5


def test_frame_records_command_state_and_outcome():
    rec = Recorder()
    run_session(
        MockClient(accuracy=1.0, rng=random.Random(0)),
        grid=8, agents=4, npcs=4, tick_ms=10_000, n_commands=3, seed=0,
        recorder=rec,
    )
    f = rec.frames[0]
    assert f.step == 0
    assert isinstance(f.command_text, str) and f.command_text
    # before/after snapshot every agent (controlled + NPCs) as (name, x, y, controlled)
    assert len(f.before) == 8 and len(f.after) == 8
    for name, x, y, controlled in f.before:
        assert isinstance(name, str) and isinstance(x, int) and isinstance(controlled, bool)
    # accuracy 1.0 + a huge tick budget -> correct and not a deadline miss
    assert f.correct is True
    assert f.missed is False
    assert f.latency_ms >= 0.0


def test_no_recorder_leaves_behavior_unchanged():
    # run_session without a recorder still returns Metrics and does not error
    m = run_session(
        MockClient(accuracy=1.0, rng=random.Random(0)),
        grid=8, agents=4, npcs=4, tick_ms=10_000, n_commands=3, seed=0,
    )
    assert m.report()["commands"] == 3
