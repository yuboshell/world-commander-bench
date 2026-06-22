"""The commander (E3) — the human's role, played by a stand-in in automated runs.

In deployment a *human* watches the panel and issues the order. For automated runs a
stand-in plays that role: MockCommander is scripted (no GPU); LLMCommander is an LLM
that views the world state, reasons, and issues a natural-language order — a stand-in
for the human commander. Either way the order refers to the lit button; the *executor*
(desk/executor.py) then grounds it, and the executor's processing time is what
we measure.
"""
from __future__ import annotations

import random

from .commands import DeskCommand, sample_command
from .world import DeskWorld

SYSTEM = ("You are a human commander watching a panel of coloured buttons. One button is "
          "lit. In ONE short imperative sentence, order your teammate to press the lit "
          "button, referring to it by its colour. Reply with only the order.")


class MockCommander:
    """Scripted stand-in — issues a reference command to the lit button (no GPU)."""

    def command(self, world: DeskWorld, rng: random.Random) -> DeskCommand:
        return sample_command(world, rng)


class LLMCommander:
    """LLM stand-in for the human: views the state, reasons, and issues the order."""

    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def command(self, world: DeskWorld, rng: random.Random) -> DeskCommand:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": world.render_text() + "\nYour order:"}],
            temperature=0.3, max_tokens=24,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        text = (resp.choices[0].message.content or "").strip().strip('"')
        # The order targets the lit button regardless of how the commander phrased it.
        return DeskCommand(text=text or "Press the lit button.",
                           acceptable={world.lit}, kind="llm")
