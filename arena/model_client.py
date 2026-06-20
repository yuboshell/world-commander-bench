"""Model clients.

RealClient talks to any OpenAI-compatible server (vLLM). MockClient lets the
harness run with no GPU — for offline smoke tests and CI.
"""
from __future__ import annotations

import json
import random
import re

from .commands import Command
from .world import DIRECTIONS, GridWorld

SYSTEM = (
    "You command agents in a grid world. Translate the order into moves. "
    'Reply with ONLY a JSON list of moves like [{"agent":"red","dir":"N"}]. '
    "Directions are N, S, E, W. Move only the agents the order names."
)


def build_prompt(world: GridWorld, command: Command) -> str:
    return f"{world.render_text()}\nOrder: \"{command.text}\"\nMoves:"


def parse_moves(reply: str) -> set[tuple[str, str]]:
    """Extract the (agent, dir) set from a model reply; tolerant of stray text."""
    match = re.search(r"\[.*\]", reply, re.DOTALL)
    if not match:
        return set()
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return set()
    out: set[tuple[str, str]] = set()
    for m in data if isinstance(data, list) else []:
        try:
            agent, direction = str(m["agent"]), str(m["dir"]).upper()
        except (TypeError, KeyError):
            continue
        if direction in DIRECTIONS:
            out.add((agent, direction))
    return out


class RealClient:
    """OpenAI-compatible chat client (vLLM, etc.)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI  # imported lazily so --mock needs no install

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def act(self, world: GridWorld, command: Command) -> set[tuple[str, str]]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": build_prompt(world, command)},
            ],
            temperature=0.0,
            max_tokens=128,
        )
        return parse_moves(resp.choices[0].message.content or "")


class MockClient:
    """No model. Returns the ground truth with probability `accuracy`, else a
    wrong move — enough to exercise the harness, metrics, and CI offline."""

    def __init__(self, accuracy: float = 0.9, rng: random.Random | None = None):
        self.accuracy = accuracy
        self.rng = rng or random.Random()

    def act(self, world: GridWorld, command: Command) -> set[tuple[str, str]]:
        if self.rng.random() < self.accuracy:
            return command.ground_truth()
        wrong = self.rng.choice([d for d in DIRECTIONS if d != command.direction])
        return {(command.targets[0], wrong)}
