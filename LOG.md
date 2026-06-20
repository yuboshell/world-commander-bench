# Activity Log

Append-only record of work sessions. Newest first.

---

## 2026-06-19 — First real grounding/latency run on amax41

**Goal:** set up venv, confirm served vLLM model, write `.env`, run the arena (mock then real), report grounding/latency/deadline misses.

**Actions:**
1. `git pull` — fast-forward `8b61f36 → 3cd724d` (added `CLAUDE.md`).
2. Created `.venv` (Python 3.11), installed `requirements.txt` (openai, python-dotenv, pytest).
3. Confirmed endpoint: `curl localhost:8000/v1/models` → `Qwen/Qwen3-14B-AWQ`, `max_model_len 16384`. vLLM TP=2 on GPU 0+1 (GPU 2 free); shared with the inventory bot.
4. Wrote `.env` (matches `.env.example` default model).
5. Mock run: `--mock --commands 50` → grounding 0.90, 0 deadline miss (plumbing OK).
6. Real smoke (5 cmds) → grounding **0.0**, 100% miss, ~4 s latency. Diagnosed: Qwen3 thinking mode eats the 128-token budget (`finish_reason: length`), no JSON emitted.
7. Fixed `arena/model_client.py`: added `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`. Verified clean JSON in 12 tokens.
8. Full real run: `--commands 200 --tick-ms 500` → grounding **1.00**, deadline-miss **0.385**, latency mean 609 ms / p50 444 / p95 1079. Saved `runs/qwen3-14b-awq_200.json`.
9. `pytest -q` → 5 passed.
10. Wrote `REPORT.md` + this `LOG.md`.

**Outcome:** first real grounding (1.00) and latency numbers captured. Deadline misses (~40%) are real-time-clock pressure under shared-GPU contention.

**Decisions pending:** visualization output format (image/GIF/video) and transfer method to MacBook (GitHub vs Google Drive).
