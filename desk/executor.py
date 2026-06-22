"""Executors for the button desk (E3 / L0).

The executor is the LLM's role: read the desk state + the command, and ground it to a
button to press (return the set of pressed indices). MockDeskExecutor needs no GPU;
RealDeskExecutor calls an OpenAI-compatible server (vLLM), reusing the arena's
no-think + small-output pattern. The reply is just the colour of the button to press.
"""
from __future__ import annotations

import random

from .commands import DeskCommand
from .world import DeskWorld

SYSTEM = ("You control a hand at a desk of coloured buttons. Read the state and the "
          "order, then reply with ONLY the colour of the single button to press "
          "(e.g. 'red'). No other words.")


def _parse(reply: str, world: DeskWorld) -> set[int]:
    r = (reply or "").lower()
    for i, b in enumerate(world.buttons):
        if b.name in r:
            return {i}
    return set()


class MockDeskExecutor:
    """Returns the correct target with probability `accuracy`, else a wrong button."""

    def __init__(self, accuracy: float = 0.95, rng: random.Random | None = None):
        self.accuracy = accuracy
        self.rng = rng or random.Random()

    def act(self, world: DeskWorld, command: DeskCommand) -> set[int]:
        if self.rng.random() < self.accuracy:
            return set(command.acceptable)
        others = [i for i in range(len(world.buttons)) if i not in command.acceptable]
        return {self.rng.choice(others)} if others else set(command.acceptable)


class RealDeskExecutor:
    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def act(self, world: DeskWorld, command: DeskCommand) -> set[int]:
        prompt = f"{world.render_text()}\nOrder: \"{command.text}\"\nButton colour to press:"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=8,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        return _parse(resp.choices[0].message.content or "", world)
