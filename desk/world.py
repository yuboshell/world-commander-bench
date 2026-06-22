"""The button desk (E3 / L0).

A character sits at a desk with a row of buttons at fixed positions (0.0 = left
edge .. 1.0 = right edge) and a hand somewhere along it. One button is lit. Pressing
a button is a **timed reach**: the hand travels |hand - button| at a fixed speed, so
acting costs physical time — the new axis E3 adds. No renderer (L0); this is the pure
state + a reach-time model + a text rendering for the LLM prompt.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

COLOURS = ["red", "blue", "green", "yellow", "purple", "orange"]


@dataclass
class Button:
    name: str    # colour label, also used for "press the red button"
    x: float     # position along the desk, 0.0 (left) .. 1.0 (right)


@dataclass
class DeskWorld:
    buttons: list[Button]
    hand_x: float
    lit: int | None        # index of the lit button, or None (all dark)
    speed: float = 1.0     # desk-units per second
    rest_x: float = 0.0    # home position the hand returns to between presses

    @classmethod
    def make(cls, n: int = 2, hand_x: float = 0.0, speed: float = 1.0,
             rest_x: float = 0.0, rng: random.Random | None = None) -> "DeskWorld":
        if n > len(COLOURS):
            raise ValueError(f"at most {len(COLOURS)} buttons")
        xs = [(i + 1) / (n + 1) for i in range(n)]      # evenly spaced, interior
        return cls(buttons=[Button(COLOURS[i], xs[i]) for i in range(n)],
                   hand_x=hand_x, lit=None, speed=speed, rest_x=rest_x)

    def reset_hand(self) -> None:
        """Return the hand to its rest position (between rounds, hands relax)."""
        self.hand_x = self.rest_x

    def reach_ms(self, button_idx: int) -> float:
        """Wall-clock ms for the hand to reach the button (distance / speed)."""
        dist = abs(self.hand_x - self.buttons[button_idx].x)
        return dist / self.speed * 1000.0

    def press(self, button_idx: int) -> None:
        """Apply a press: the hand ends up at the pressed button (carries over)."""
        self.hand_x = self.buttons[button_idx].x

    def render_text(self) -> str:
        bs = ", ".join(f"{b.name} at {b.x:.2f}" for b in self.buttons)
        lit = self.buttons[self.lit].name if self.lit is not None else "none"
        return (f"Desk buttons (position 0.00=left .. 1.00=right): {bs}. "
                f"Your hand is at {self.hand_x:.2f}. Lit button: {lit}.")
