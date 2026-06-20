"""Command schema, natural-language phrasing, and ground-truth resolution.

A command targets one or more controlled agents and a direction. The harness
knows the ground-truth move set; the model must reproduce it from the phrasing
and the world state. Grounding accuracy is exact set match.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .world import DIRECTIONS, GridWorld

DIR_WORD = {"N": "north", "S": "south", "E": "east", "W": "west"}


@dataclass
class Command:
    targets: list[str]   # controlled agent names this command moves
    direction: str       # N / S / E / W
    text: str            # the natural-language phrasing shown to the model

    def ground_truth(self) -> set[tuple[str, str]]:
        return {(t, self.direction) for t in self.targets}


def sample_command(world: GridWorld, rng: random.Random) -> Command:
    """Sample a command. Single-target and 'all-except' group forms for now.

    TODO: memory commands ("the one I sent west earlier, now move it north")
    need session history threaded through the harness. TODO: region/colour-family
    group predicates.
    """
    ctrl = world.controlled()
    direction = rng.choice(list(DIRECTIONS))
    word = DIR_WORD[direction]

    if len(ctrl) >= 3 and rng.random() < 0.3:
        # group form: "every agent except the yellow one, move east"
        excluded = rng.choice(ctrl)
        targets = [a.name for a in ctrl if a.name != excluded.name]
        text = f"Every agent except the {excluded.name} one, move {word}."
        return Command(targets, direction, text)

    # single form: "move the red agent north"
    a = rng.choice(ctrl)
    text = f"Move the {a.name} agent {word}."
    return Command([a.name], direction, text)
