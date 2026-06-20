# World Commander Bench — Run Report

**Date:** 2026-06-19
**Machine:** amax41 (3× RTX 2080 Ti)
**Served model:** `Qwen/Qwen3-14B-AWQ` via vLLM (OpenAI-compatible, `localhost:8000/v1`)
**vLLM config:** TP=2 (GPU 0+1), AWQ, `--enforce-eager`, `max_model_len 16384`, `dtype half`
**Note:** the same vLLM instance also serves the Lab Inventory Bot, so the GPU is *shared* — latency carries contention noise.

## Endpoint confirmation
```
$ curl localhost:8000/v1/models
→ id: "Qwen/Qwen3-14B-AWQ", max_model_len: 16384
```
Matches the `.env.example` default; `.env` written accordingly.

## Results

| Run | Commands | Grounding | Deadline-miss | Latency mean | p50 | p95 |
|-----|----------|-----------|---------------|--------------|-----|-----|
| Mock (`--mock`) | 50 | 0.90 | 0.00 | ~0 ms | ~0 | ~0 |
| **Real, 500 ms tick** | **200** | **1.00** | **0.385** | **609 ms** | **444 ms** | **1079 ms** |

Saved: `runs/qwen3-14b-awq_200.json` (gitignored).

### Reading the numbers
- **Grounding 1.00** — at the current scale (8×8 grid, 4 agents, 4 NPCs) the model resolves every command (single-target and "all-except" group forms). Deterministic (temperature 0).
- **Deadline misses ~0.39** — ~40% of commands exceed the 500 ms tick budget. p50 (444 ms) sits right on the line, so the rate is sensitive and wobbles run-to-run (observed 0.385–0.425) under shared-GPU contention. p95 ~1080 ms is the tail.
- **Mock** numbers validate plumbing only: `MockClient` returns ground truth with p=0.9 instantly.

## Key finding — Qwen3 thinking mode
The first real run gave **grounding 0.0, 100% deadline miss, ~4000 ms latency**. Root cause: Qwen3-14B defaults to *thinking* mode and spent the entire 128-token budget inside `<think>` (`finish_reason: length`), never emitting the JSON → `parse_moves` returned empty every time.

**Fix:** `RealClient.act` now passes `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`. Verified: the model then returns `[{"agent":"red","dir":"N"}]` in 12 tokens (`finish: stop`). Grounding 0.0 → 1.0; latency ~4000 ms → ~600 ms.

## Validation
- `pytest -q` → 5 passed.

## Next steps (open TODOs from CLAUDE.md / code)
- Concurrent clock (world ticks on a timer thread while the model thinks).
- Memory / region commands.
- Efficiency sweep (KV-cache policy, VRAM budgets) — needs our **own** controllable vLLM, not the shared instance.
- Optional: per-tick state capture for visualization (see LOG.md discussion).
