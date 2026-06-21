"""Tests for command sampling — coverage of the command forms."""
import random

from arena.commands import sample_command
from arena.world import GridWorld

CONTROLLED = {"red", "blue", "green", "yellow"}


def _samples(n=400, agents=4, npcs=4, seed=0):
    rng = random.Random(seed)
    world = GridWorld.random_init(8, agents, npcs, rng=rng)
    return [sample_command(world, rng) for _ in range(n)]


def _is_positive_multi(c):
    return len(c.targets) >= 2 and "except" not in c.text.lower()


def test_positive_multi_target_commands_are_issued():
    # "Move the blue and green agents north." — naming 2+ agents positively.
    assert any(_is_positive_multi(c) for c in _samples()), \
        "sampler should issue positive multi-agent commands, not only single + all-except"


def test_all_three_command_forms_appear():
    cmds = _samples()
    assert any(len(c.targets) == 1 for c in cmds)                  # single-target
    assert any(_is_positive_multi(c) for c in cmds)                # positive subset
    assert any("except" in c.text.lower() for c in cmds)          # all-except group


def test_positive_subset_is_consistent():
    for c in _samples():
        if _is_positive_multi(c):
            assert len(set(c.targets)) == len(c.targets), "no repeated agents"
            assert set(c.targets) <= CONTROLLED
            dirs = {d for ds in c.acceptable.values() for d in ds}
            assert len(dirs) == 1, "micro subset shares one direction"
            (only_dir,) = dirs
            assert c.ground_truth() == {(t, only_dir) for t in c.targets}
            assert " agents " in c.text and c.text.endswith(".")
            for name in c.targets:
                assert name in c.text


def test_positive_subset_sizes_two_and_three_occur():
    sizes = {len(c.targets) for c in _samples() if _is_positive_multi(c)}
    assert 2 in sizes and 3 in sizes, f"expected subsets of size 2 and 3, saw {sizes}"
