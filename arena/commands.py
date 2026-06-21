"""Command schema, natural-language phrasing, and ground-truth resolution.

Two granularities, one channel and one action space (sets of (agent, direction)):

- **micro** — names the agents and a direction explicitly ("move the red agent
  north"). Tests reference resolution; each target has exactly one correct move.
- **macro** — a single goal whose per-agent moves must be computed from world
  state ("everyone move toward the center", "flee the nearest enemy"). Tests
  spatial reasoning; each target has an *acceptable set* of moves (any that make
  progress), so grounding is "every commanded agent moved, and each move is in its
  acceptable set" rather than exact-single-answer.

Both are scored by `Command.is_correct`; for micro the acceptable sets are
singletons, so it reduces to exact match.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .world import DIRECTIONS, GridWorld

DIR_WORD = {"N": "north", "S": "south", "E": "east", "W": "west"}

MICRO_FORMS = ["single", "subset", "all_except"]
MACRO_FORMS = ["converge", "scatter", "home", "flee"]


@dataclass
class Command:
    text: str                          # the natural-language phrasing shown to the model
    acceptable: dict[str, set[str]]    # agent name -> acceptable directions (singleton for micro)
    granularity: str = "micro"         # "micro" | "macro"

    @property
    def targets(self) -> list[str]:
        return list(self.acceptable.keys())

    def ground_truth(self) -> set[tuple[str, str]]:
        """One canonical acceptable move per target (deterministic) — for display,
        a mock's correct answer, and back-compat. Scoring uses `is_correct`."""
        return {(n, sorted(ds)[0]) for n, ds in self.acceptable.items() if ds}

    def is_correct(self, action: set[tuple[str, str]]) -> bool:
        """Exactly the commanded agents moved, and each move is acceptable."""
        if {n for n, _ in action} != set(self.acceptable):
            return False
        return all(d in self.acceptable.get(n, set()) for n, d in action)


# --- geometry: which single steps make progress toward / away from a point ---

def _step(size: int, x: int, y: int, d: str) -> tuple[int, int]:
    dx, dy = DIRECTIONS[d]
    return max(0, min(size - 1, x + dx)), max(0, min(size - 1, y + dy))


def _dist(x: float, y: float, tx: float, ty: float) -> float:
    return abs(x - tx) + abs(y - ty)


def toward_dirs(size: int, ax: int, ay: int, tx: float, ty: float) -> set[str]:
    """Directions whose (clamped) step strictly reduces Manhattan distance to the target."""
    cur = _dist(ax, ay, tx, ty)
    return {d for d in DIRECTIONS if _dist(*_step(size, ax, ay, d), tx, ty) < cur}


def away_dirs(size: int, ax: int, ay: int, tx: float, ty: float) -> set[str]:
    """Directions whose (clamped) step strictly increases distance (wall-blocked steps don't count)."""
    cur = _dist(ax, ay, tx, ty)
    return {d for d in DIRECTIONS if _dist(*_step(size, ax, ay, d), tx, ty) > cur}


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _micro(world: GridWorld, form: str, rng: random.Random) -> Command:
    ctrl = world.controlled()
    direction = rng.choice(list(DIRECTIONS))
    word = DIR_WORD[direction]
    if form == "all_except":
        excluded = rng.choice(ctrl)
        names = [a.name for a in ctrl if a.name != excluded.name]
        text = f"Every agent except the {excluded.name} one, move {word}."
    elif form == "subset":
        k = rng.randint(2, len(ctrl))
        names = [a.name for a in rng.sample(ctrl, k)]
        text = f"Move the {_join_names(names)} agents {word}."
    else:  # single
        names = [rng.choice(ctrl).name]
        text = f"Move the {names[0]} agent {word}."
    return Command(text=text, acceptable={n: {direction} for n in names}, granularity="micro")


def _macro(world: GridWorld, form: str, rng: random.Random) -> Command:
    ctrl = world.controlled()
    size = world.size
    acc: dict[str, set[str]] = {}
    if form in ("converge", "scatter"):
        cx = cy = (size - 1) / 2.0
        pick = toward_dirs if form == "converge" else away_dirs
        for a in ctrl:
            ds = pick(size, a.x, a.y, cx, cy)
            if ds:
                acc[a.name] = ds
        text = ("All agents, move toward the center of the grid." if form == "converge"
                else "All agents, spread out away from the center of the grid.")
    elif form == "home":
        for a in ctrl:
            ds = toward_dirs(size, a.x, a.y, 0, 0)
            if ds:
                acc[a.name] = ds
        text = "All agents, return to base at the top-left corner (0,0)."
    else:  # flee — away from each agent's nearest uncontrolled agent
        npcs = [a for a in world.agents if not a.controlled]
        for a in ctrl:
            if not npcs:
                break
            near = min(npcs, key=lambda n: abs(n.x - a.x) + abs(n.y - a.y))
            ds = away_dirs(size, a.x, a.y, near.x, near.y)
            if ds:
                acc[a.name] = ds
        text = "All agents, move away from the nearest uncontrolled agent."
    return Command(text=text, acceptable=acc, granularity="macro")


def _form_valid(form: str, world: GridWorld) -> bool:
    n = len(world.controlled())
    if form == "subset":
        return n >= 2
    if form == "all_except":
        return n >= 3
    if form == "flee":
        return n >= 1 and any(not a.controlled for a in world.agents)
    return n >= 1  # single + converge/scatter/home


def sample_command(world: GridWorld, rng: random.Random,
                   forms: list[str] | None = None) -> Command:
    """Sample a command from a form pool. Default pool is micro (single / subset /
    all_except); pass `forms=MACRO_FORMS` (or specific names) for macro goals.
    Retries if a macro form degenerates to no movable agents (all at target)."""
    forms = forms or MICRO_FORMS
    valid = [f for f in forms if _form_valid(f, world)] or ["single"]
    for _ in range(5):
        form = rng.choice(valid)
        cmd = _micro(world, form, rng) if form in MICRO_FORMS else _macro(world, form, rng)
        if cmd.acceptable:
            return cmd
    return _micro(world, "single", rng)
