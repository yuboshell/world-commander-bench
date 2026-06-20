"""World + grounding tests — no model, so CI runs anywhere."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena.commands import sample_command           # noqa: E402
from arena.harness import run_session               # noqa: E402
from arena.model_client import MockClient, parse_moves   # noqa: E402
from arena.world import DIRECTIONS, GridWorld        # noqa: E402


def test_move_clamps_to_grid():
    w = GridWorld.random_init(4, 1, 0, rng=random.Random(0))
    a = w.controlled()[0]
    a.x, a.y = 0, 0
    w.apply([(a.name, "W")])   # off the left edge
    w.apply([(a.name, "N")])   # off the top edge
    assert 0 <= a.x < 4 and 0 <= a.y < 4


def test_ground_truth_targets_controlled_agents_only():
    w = GridWorld.random_init(8, 4, 2, rng=random.Random(1))
    names = {a.name for a in w.controlled()}
    cmd = sample_command(w, random.Random(2))
    gt = cmd.ground_truth()
    assert all(name in names for name, _ in gt)
    assert all(d in DIRECTIONS for _, d in gt)


def test_parse_moves_tolerates_noise():
    reply = 'Sure! [{"agent":"red","dir":"n"}, {"agent":"blue","dir":"E"}] done'
    assert parse_moves(reply) == {("red", "N"), ("blue", "E")}


def test_parse_moves_empty_on_garbage():
    assert parse_moves("no json here") == set()


def test_perfect_mock_scores_clean():
    m = run_session(MockClient(accuracy=1.0), grid=8, agents=4, npcs=3,
                    tick_ms=10_000, n_commands=50, seed=0)
    rep = m.report()
    assert rep["grounding_accuracy"] == 1.0
    assert rep["deadline_miss_rate"] == 0.0
    assert rep["commands"] == 50
