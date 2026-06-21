"""Macro commands: a single goal whose per-agent moves are computed from world
state (converge/scatter/home/flee), scored by acceptable-set grounding (any move
that makes progress counts). Contrast with micro commands, which name agents and
a direction explicitly. Geometry values below are hand-computed (8x8 grid, N
decreases y, moves clamp at edges)."""
import random

from arena.commands import (MACRO_FORMS, MICRO_FORMS, Command, away_dirs,
                            sample_command, toward_dirs)
from arena.world import Agent, GridWorld


def test_toward_dirs_reduce_distance():
    assert toward_dirs(8, 2, 4, 4, 4) == {"E"}            # only x differs
    assert toward_dirs(8, 0, 0, 5, 5) == {"E", "S"}       # both axes
    assert toward_dirs(8, 4, 4, 4, 4) == set()            # already at target


def test_away_dirs_increase_distance_and_respect_walls():
    assert away_dirs(8, 2, 4, 4, 4) == {"W", "N", "S"}    # W increases x; N/S increase y-dist
    assert away_dirs(8, 0, 0, 5, 5) == set()              # cornered: N/W clamp, E/S reduce
    assert away_dirs(8, 4, 4, 4, 4) == {"N", "S", "E", "W"}  # at target: any move increases


def _two_agent_world():
    return GridWorld(size=8, agents=[Agent("red", 0, 0, True),
                                     Agent("blue", 7, 7, True)])


def test_converge_acceptable_sets_and_grounding():
    cmd = sample_command(_two_agent_world(), random.Random(0), forms=["converge"])
    assert cmd.granularity == "macro"
    assert cmd.acceptable["red"] == {"E", "S"}            # toward center (3.5,3.5) from (0,0)
    assert cmd.acceptable["blue"] == {"W", "N"}           # toward center from (7,7)
    assert cmd.is_correct({("red", "E"), ("blue", "N")})  # one acceptable each
    assert cmd.is_correct({("red", "S"), ("blue", "W")})  # the other acceptable each
    assert not cmd.is_correct({("red", "N"), ("blue", "N")})  # red N moves away
    assert not cmd.is_correct({("red", "E")})             # blue not moved


def test_micro_is_exact_match():
    w = GridWorld.random_init(8, 3, 2, rng=random.Random(1))
    cmd = sample_command(w, random.Random(3))             # default = micro
    assert cmd.granularity == "micro"
    assert cmd.is_correct(cmd.ground_truth())             # the canonical answer is correct
    # flip one agent's direction -> wrong
    gt = sorted(cmd.ground_truth())
    bad = next(d for d in ("N", "S", "E", "W") if (gt[0][0], d) not in cmd.ground_truth())
    assert not cmd.is_correct({(gt[0][0], bad)} | set(gt[1:]))


def test_agent_grounding_gives_partial_credit():
    cmd = Command(text="x", granularity="macro",
                  acceptable={"red": {"E", "S"}, "green": {"N", "W"}, "yellow": {"W"}})
    # red ok, green ok, yellow wrong; blue is extra (not movable) -> ignored
    c, t = cmd.agent_grounding({("red", "E"), ("green", "W"), ("yellow", "N"), ("blue", "S")})
    assert (c, t) == (2, 3)
    # an omitted movable agent counts as wrong, not ignored
    assert cmd.agent_grounding({("red", "E")}) == (1, 3)
    # empty action -> nothing right
    assert cmd.agent_grounding(set()) == (0, 3)


def test_sample_command_selects_by_form_pool():
    w = GridWorld.random_init(8, 4, 2, rng=random.Random(5))
    assert sample_command(w, random.Random(0)).granularity == "micro"
    assert sample_command(w, random.Random(0), forms=MACRO_FORMS).granularity == "macro"
    assert set(MICRO_FORMS).isdisjoint(MACRO_FORMS)
