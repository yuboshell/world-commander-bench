"""E3 embodiment env (L0) — pure-Python button desk.

A button lights for a window W; the command refers to the lit button (by "lit",
colour, or side); the LLM executor grounds it to a button; pressing is a TIMED
reach (distance / speed). Success = grounded correctly AND parse+ground latency +
reach time <= W. Values below are hand-computed.
"""
import random

from desk.world import Button, DeskWorld
from desk.commands import DeskCommand, sample_command
from desk.eval import round_success, success_curve


def _w(lit, hand=0.0, speed=1.0):
    return DeskWorld(buttons=[Button("red", 0.0), Button("blue", 1.0)],
                     hand_x=hand, lit=lit, speed=speed)


def test_reach_ms_is_distance_over_speed():
    w = _w(lit=1, hand=0.0, speed=2.0)
    assert w.reach_ms(1) == 500.0   # dist 1.0 / 2.0 u/s = 0.5 s
    assert w.reach_ms(0) == 0.0     # hand already at red


def test_reset_hand_returns_to_rest():
    w = DeskWorld(buttons=[Button("red", 0.0), Button("blue", 1.0)], hand_x=1.0,
                  lit=0, speed=1.0, rest_x=0.0)
    w.reset_hand()
    assert w.hand_x == 0.0


def test_render_text_states_positions_and_lit():
    t = _w(lit=0).render_text()
    assert "red" in t and "blue" in t and "Lit button: red" in t


def test_command_always_refers_to_the_lit_button():
    w = _w(lit=1)   # blue (right) is lit
    for kind in ("direct", "colour", "spatial"):
        cmd = sample_command(w, random.Random(0), kind=kind)
        assert cmd.acceptable == {1}
        assert cmd.is_correct({1}) and not cmd.is_correct({0})
    assert "blue" in sample_command(w, random.Random(0), kind="colour").text
    assert "right" in sample_command(w, random.Random(0), kind="spatial").text
    assert "lit" in sample_command(w, random.Random(0), kind="direct").text


def test_round_success_needs_grounding_and_time():
    assert round_success(True, 300, 500, 1000) is True    # 800 <= 1000
    assert round_success(True, 600, 500, 1000) is False   # 1100 > 1000 (too slow)
    assert round_success(False, 100, 100, 1000) is False  # wrong button


def test_success_curve_over_windows():
    rounds = [(True, 300, 200), (True, 900, 200), (False, 100, 100)]
    assert success_curve(rounds, [1000])[0]["success_rate"] == 1 / 3
    assert success_curve(rounds, [2000])[0]["success_rate"] == 2 / 3  # both grounded fit
