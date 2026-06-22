"""Commands for the button desk (E3 / L0).

Every command refers to the **lit** button — the task is to press it before it goes
dark — but it refers to it in different ways, exactly the reference taxonomy from the
arena (E1): direct, colour, or spatial. The executor's job is to resolve the
reference to the right button (grounding); planning is not involved (the human/the
environment already chose what to press). Scored by exact match on the target.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .world import DeskWorld

REF_KINDS = ["direct", "colour", "spatial"]


@dataclass
class DeskCommand:
    text: str
    acceptable: set[int]    # the target button index/indices (the lit button)
    kind: str

    def is_correct(self, action: set[int]) -> bool:
        return action == self.acceptable


def _side(world: DeskWorld, idx: int) -> str:
    xs = [b.x for b in world.buttons]
    if world.buttons[idx].x == min(xs):
        return "left"
    if world.buttons[idx].x == max(xs):
        return "right"
    return "middle"


def sample_command(world: DeskWorld, rng: random.Random, kind: str | None = None) -> DeskCommand:
    """A command referring to the currently lit button by `kind` (default random)."""
    k = world.lit
    if k is None:
        raise ValueError("no button is lit")
    kind = kind or rng.choice(REF_KINDS)
    if kind == "direct":
        text = "Press the lit button."
    elif kind == "colour":
        text = f"Press the {world.buttons[k].name} button."
    else:  # spatial
        text = f"Press the {_side(world, k)} button."
    return DeskCommand(text=text, acceptable={k}, kind=kind)
