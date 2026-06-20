# World Commander Bench — agent guide

The implementation repo for the **World Commander** program's Phase-1 benchmark.
This repo is **code only**; the canonical research docs (proposal, literature,
decisions) live in the separate private repo `DreamSoul-AI/world-commander` — clone
it and read its `index.md` if you need the *why*.

## What's here
- The **command arena**: a minimal grid world where colour-tagged agents move in one
  of four directions on streamed commands. A few **uncontrolled NPCs** move on their
  own each tick, so the clock never pauses and a command that arrives late concedes
  ground. One command is trivial; the test is the **stream** — many, fast.
- Measured: **grounding accuracy**, **command-to-action latency**, **deadline misses**.
- The StarCraft II real-time harness comes later in this same repo (it shares the
  streaming-command core). When it does, vendor references (TextStarCraft II,
  LLM-PySC2) into a gitignored `reference/` dir rather than reinventing the interface.

## Layout
- `arena/` — `world.py` (grid + NPCs), `commands.py` (schema + ground truth),
  `model_client.py` (vLLM + mock clients), `harness.py` (the streaming loop),
  `metrics.py`, `config.py`.
- `scripts/run_arena.py` — run a session; `--mock` needs no GPU.
- `tests/` — world + grounding tests, no model needed (`pytest -q`).

## Run
```
python -m venv .venv && source .venv/bin/activate   # Alliance: follow your alliance.md venv rules
pip install -r requirements.txt
cp .env.example .env                                 # set WCB_BASE_URL + WCB_MODEL
python scripts/run_arena.py --mock --commands 50     # offline smoke test
python scripts/run_arena.py --commands 200 --tick-ms 500   # against a served model
```

## Where it runs (compute)
- Develop on the MacBook (editor); **run on amax41** (3x RTX 2080 Ti, headless)
  against its already-deployed vLLM — an OpenAI-compatible API, so no model download.
- Confirm the endpoint and model on the box: `curl localhost:8000/v1/models`, or
  `ps aux | grep -i vllm` for the port. Put them in `.env` (the default model in
  `.env.example` is `Qwen3-14B-AWQ` — verify it matches what is actually served).
- `yubopc` (RTX 4060, 8 GB, modern consumer GPU) is the later consumer-GPU
  measurement box; Alliance for the 1B-70B sweep.
- The shared deployed model is fine for command-following validation. The efficiency
  sweep (KV-cache policy, VRAM budgets) needs **our own** controllable vLLM instance —
  a later step, not the first run.

## Conventions
- The harness is **light**: a pure-Python world plus one HTTP call to a served model.
  Heavy deps (vLLM, torch) live on the serving machine, never in `requirements.txt`.
- **Never hard-code the endpoint or model** — they differ per machine, so they live in
  `.env` (gitignored).
- Gitignore venvs, `.env`, and run outputs; commit source + configs only.
- **Multi-device sync:** this repo is cloned on several machines and edited with Claude
  Code on each. **Pull before you work, push after** — the one habit that avoids conflicts.
- Keep it minimal and match the existing style; mark unfinished directions `TODO`.

## Status
Scaffold, validated offline (mock run + `pytest`). **Next: run on amax against the
deployed model** for the first grounding and latency numbers. Open `TODO`s in code:
memory/region commands, a concurrent clock (the world ticking while the model thinks),
and the efficiency sweep.
