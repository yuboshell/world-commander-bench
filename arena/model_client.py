"""Model clients.

RealClient talks to any OpenAI-compatible server (vLLM). MockClient lets the
harness run with no GPU — for offline smoke tests and CI.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Callable

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
    """Verbose JSON schema: [{"agent":"red","dir":"N"}]. Tolerant of stray text."""
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


def parse_pairs(reply: str) -> set[tuple[str, str]]:
    """Terse pairs schema: "red:N blue:S" (one agent:dir token each)."""
    out: set[tuple[str, str]] = set()
    for agent, direction in re.findall(r"([A-Za-z]+)\s*:\s*([NSEWnsew])\b", reply):
        out.add((agent.lower(), direction.upper()))
    return out


def parse_grouped(reply: str) -> set[tuple[str, str]]:
    """Terse grouped schema: "N: red blue" (one direction, then its agents).
    Shortest when many agents share a direction — as arena commands always do."""
    out: set[tuple[str, str]] = set()
    for direction, names in re.findall(r"([NSEWnsew])\s*:\s*([A-Za-z, ]+)", reply):
        for agent in re.findall(r"[A-Za-z]+", names):
            out.add((agent.lower(), direction.upper()))
    return out


@dataclass
class Schema:
    name: str
    system: str
    parse: Callable[[str], set[tuple[str, str]]]


SCHEMAS: dict[str, Schema] = {
    "json": Schema("json", SYSTEM, parse_moves),
    "pairs": Schema(
        "pairs",
        "You command agents in a grid world. Translate the order into moves. "
        'Reply with ONLY space-separated agent:direction pairs like "red:N blue:S". '
        "Directions are N, S, E, W. Move only the agents the order names.",
        parse_pairs,
    ),
    "grouped": Schema(
        "grouped",
        "You command agents in a grid world. Translate the order into moves. "
        "The named agents all move the same direction; reply with ONLY the "
        'direction then the agents, like "N: red blue". '
        "Directions are N, S, E, W. Move only the agents the order names.",
        parse_grouped,
    ),
}


class RealClient:
    """OpenAI-compatible chat client (vLLM, etc.). `schema` selects the output
    format (system prompt + parser) so different schemas can be compared."""

    def __init__(self, base_url: str, api_key: str, model: str, schema: str = "json"):
        from openai import OpenAI  # imported lazily so --mock needs no install

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.schema = SCHEMAS[schema] if isinstance(schema, str) else schema

    def act(self, world: GridWorld, command: Command) -> set[tuple[str, str]]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.schema.system},
                {"role": "user", "content": build_prompt(world, command)},
            ],
            temperature=0.0,
            max_tokens=128,
            # Reasoning models (Qwen3 etc.) otherwise spend the whole token
            # budget on <think> and never emit the answer. The arena wants a
            # direct action under a real-time clock, so turn thinking off.
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return self.schema.parse(resp.choices[0].message.content or "")


class MockClient:
    """No model. Returns the ground truth with probability `accuracy`, else a
    wrong move — enough to exercise the harness, metrics, and CI offline."""

    def __init__(self, accuracy: float = 0.9, rng: random.Random | None = None):
        self.accuracy = accuracy
        self.rng = rng or random.Random()

    def act(self, world: GridWorld, command: Command) -> set[tuple[str, str]]:
        if self.rng.random() < self.accuracy:
            return command.ground_truth()
        # deliberately wrong: move the first target in an unacceptable direction
        gt = sorted(command.ground_truth())
        name0 = gt[0][0]
        bad = next(d for d in DIRECTIONS if d not in command.acceptable.get(name0, set()))
        return {(name0, bad)} | set(gt[1:])
