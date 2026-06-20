"""Per-tick state capture for visualization.

The harness drives an optional Recorder so a session can be replayed as plots
or a grid animation without changing the (light) default run path. A Frame holds
the world before/after each command plus the command's outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# (name, x, y, controlled) — a flat, cheap snapshot of one agent.
AgentState = tuple[str, int, int, bool]


@dataclass
class Frame:
    step: int
    command_text: str
    before: list[AgentState]
    after: list[AgentState]
    correct: bool
    missed: bool
    latency_ms: float


@dataclass
class Recorder:
    frames: list[Frame] = field(default_factory=list)

    def add(self, step: int, command_text: str, before: list[AgentState],
            after: list[AgentState], correct: bool, missed: bool,
            latency_ms: float) -> None:
        self.frames.append(Frame(step, command_text, before, after,
                                 correct, missed, latency_ms))
