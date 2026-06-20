# world-commander-bench

Implementation of the **World Commander** Phase-1 benchmark: a real-time,
budget-aware test of how well and how cheaply a language model can carry out
streamed commands. It starts with the **command arena** (a minimal warm-up) and
will grow the StarCraft II real-time harness alongside it — the two share the
streaming-command core.

Research proposal and docs: the private `world-commander` repo (see its `index.md`).

## What the arena measures

A small grid world holds colour-tagged agents that move in one of four directions
on command. The room is **not single-sided**: a few uncontrolled agents move on
their own clock, so a command that arrives late concedes ground. One command is
trivial; the test is the **stream** — many commands, fast. Three quantities:

- **grounding accuracy** — did the model turn the order into the right move(s)?
- **latency** — order-to-action time.
- **deadline misses** — responses that arrived after the tick budget.

## Layout

```
arena/
  world.py         grid world: controlled agents + uncontrolled NPCs, text render
  commands.py      command schema, natural-language phrasing, ground-truth action
  model_client.py  vLLM (OpenAI-compatible) client + a mock client for offline runs
  harness.py       the streaming loop: issue -> time -> ground -> tick -> record
  metrics.py       grounding accuracy, latency (p50/p95), deadline-miss rate
  config.py        configuration from environment / .env
scripts/run_arena.py   run a session, print a report (--mock needs no GPU)
tests/                  world + grounding tests (no model needed)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: run inside WSL2
pip install -r requirements.txt
cp .env.example .env          # then edit: model endpoint + name
```

The model endpoint differs per machine, so it lives in `.env`, never in code:

- **amax** (model served locally): `WCB_BASE_URL=http://localhost:8000/v1`
- **Mac**, over an SSH tunnel (`ssh -L 8000:localhost:8000 amax41`): the same URL.

## Run

```bash
# Offline smoke test — no model, validates the harness itself:
python scripts/run_arena.py --mock --commands 50

# Against a served model (e.g. amax's vLLM):
python scripts/run_arena.py --commands 200 --tick-ms 500 --npcs 4
```

## Status

Scaffold. The core loop, grounding, latency, deadline accounting, and NPCs are in.
Open extensions are marked `TODO` in code: memory/region commands, a truly
concurrent clock (the world ticking while the model thinks), and the KV-cache /
VRAM-budget sweep — which needs our own controllable vLLM instance, not a shared one.
