"""Success + deadline-frontier logic for the button desk (E3 / L0).

A round succeeds iff the executor grounded the command to the right button AND the
whole chain — parse+ground latency (LLM) plus the reach time (body) — fits inside the
lit window. Sweeping the window gives a success-vs-deadline frontier, the E3 analog of
the arena's deadline frontier (now with a physical-execution term).
"""
from __future__ import annotations


def round_success(grounded: bool, parse_ground_ms: float, reach_ms: float,
                  window_ms: float) -> bool:
    return bool(grounded) and (parse_ground_ms + reach_ms) <= window_ms


def success_curve(rounds, windows_ms) -> list[dict]:
    """rounds: iterable of (grounded, parse_ground_ms, reach_ms).
    Returns one {window_ms, success_rate} per window."""
    rounds = list(rounds)
    n = len(rounds) or 1
    out = []
    for w in windows_ms:
        s = sum(round_success(g, p, r, w) for g, p, r in rounds) / n
        out.append({"window_ms": w, "success_rate": s})
    return out
