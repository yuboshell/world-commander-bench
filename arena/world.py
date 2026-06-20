"""The grid world: colour-tagged controlled agents plus uncontrolled NPCs.

Deliberately minimal — no graphics, no game engine. The NPCs move on their own
each tick, so the world does not pause for the model (a late command concedes
ground). Coordinates are (x, y) with the origin at the top-left; N decreases y.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

DIRECTIONS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
COLOURS = ["red", "blue", "green", "yellow", "purple", "orange", "cyan", "pink"]


@dataclass
class Agent:
    name: str          # unique tag, e.g. "red" (controlled) or "npc0" (not)
    x: int
    y: int
    controlled: bool   # False = uncontrolled NPC


@dataclass
class GridWorld:
    size: int
    agents: list[Agent] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    @classmethod
    def random_init(cls, size: int, n_controlled: int, n_npcs: int,
                    rng: random.Random | None = None) -> "GridWorld":
        if n_controlled > len(COLOURS):
            raise ValueError(f"at most {len(COLOURS)} controlled agents (unique colours)")
        if n_controlled + n_npcs > size * size:
            raise ValueError("more agents than grid cells")
        rng = rng or random.Random()
        cells = [(x, y) for x in range(size) for y in range(size)]
        rng.shuffle(cells)
        agents: list[Agent] = []
        for i in range(n_controlled):
            x, y = cells.pop()
            agents.append(Agent(COLOURS[i], x, y, controlled=True))
        for j in range(n_npcs):
            x, y = cells.pop()
            agents.append(Agent(f"npc{j}", x, y, controlled=False))
        return cls(size=size, agents=agents, rng=rng)

    def controlled(self) -> list[Agent]:
        return [a for a in self.agents if a.controlled]

    def by_name(self, name: str) -> Agent | None:
        for a in self.agents:
            if a.name == name:
                return a
        return None

    def _move(self, a: Agent, direction: str) -> None:
        dx, dy = DIRECTIONS[direction]
        a.x = max(0, min(self.size - 1, a.x + dx))
        a.y = max(0, min(self.size - 1, a.y + dy))

    def apply(self, moves: list[tuple[str, str]]) -> None:
        """Apply (agent_name, direction) moves — controlled agents only."""
        for name, direction in moves:
            a = self.by_name(name)
            if a is not None and a.controlled and direction in DIRECTIONS:
                self._move(a, direction)

    def tick_npcs(self) -> None:
        """Advance the uncontrolled agents one random step (the unpausing clock)."""
        for a in self.agents:
            if not a.controlled:
                self._move(a, self.rng.choice(list(DIRECTIONS)))

    def render_text(self) -> str:
        """Compact text state for the model prompt."""
        ctrl = ", ".join(f"{a.name} at ({a.x},{a.y})" for a in self.controlled())
        npcs = ", ".join(f"{a.name} at ({a.x},{a.y})"
                         for a in self.agents if not a.controlled)
        return (f"Grid {self.size}x{self.size} (x:0-{self.size - 1} left to right, "
                f"y:0-{self.size - 1} top to bottom; N decreases y).\n"
                f"Your agents: {ctrl}.\n"
                f"Uncontrolled (do not command these): {npcs or 'none'}.")
