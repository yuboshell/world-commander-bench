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


def _join_names(names: list[str]) -> str:
    """Natural English list: ['blue'] -> 'blue'; ['blue','green'] -> 'blue and
    green'; ['blue','green','yellow'] -> 'blue, green, and yellow'."""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def sample_command(world: GridWorld, rng: random.Random) -> Command:
    """Sample a command across three forms: single-target, a positively named
    multi-agent subset, and the 'all-except' group.

    TODO: memory commands ("the one I sent west earlier, now move it north")
    need session history threaded through the harness. TODO: region/colour-family
    group predicates.
    """
    ctrl = world.controlled()
    direction = rng.choice(list(DIRECTIONS))
    word = DIR_WORD[direction]

    forms = ["single"]
    if len(ctrl) >= 2:
        forms.append("subset")        # "move the blue and green agents north"
    if len(ctrl) >= 3:
        forms.append("all_except")    # "every agent except the yellow one, move east"
    form = rng.choice(forms)

    if form == "all_except":
        excluded = rng.choice(ctrl)
        targets = [a.name for a in ctrl if a.name != excluded.name]
        text = f"Every agent except the {excluded.name} one, move {word}."
        return Command(targets, direction, text)

    if form == "subset":
        k = rng.randint(2, len(ctrl))
        names = [a.name for a in rng.sample(ctrl, k)]
        text = f"Move the {_join_names(names)} agents {word}."
        return Command(names, direction, text)

    # single form: "move the red agent north"
    a = rng.choice(ctrl)
    text = f"Move the {a.name} agent {word}."
    return Command([a.name], direction, text)
