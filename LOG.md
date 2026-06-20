# Activity Log

Append-only record of work sessions. Newest first.

---

## 2026-06-19 — Visualization: metric plots + grid-replay MP4

**Goal:** add visual output (Yubo chose plots + grid-replay MP4, transfer via
Google Drive) and auto commit/push after each job.

**Actions:**
1. Added a `Stop` hook (`.claude/settings.json` → `.claude/hooks/auto-commit-push.sh`)
   to auto-commit + push on a dirty tree. May need `/hooks` or a restart to load
   this session (`.claude/` was created mid-session).
2. TDD: `arena/recorder.py` (`Recorder`/`Frame`) + `GridWorld.snapshot()` +
   optional `recorder=` param on `run_session`. New tests in `tests/test_recorder.py`.
3. `arena/viz.py`: `plot_metrics` (PNG) + `render_replay` (MP4 via ffmpeg).
   `scripts/visualize.py` ties it together with `--upload` to rclone Drive.
4. Probed env: matplotlib installed into `.venv` (kept out of core
   `requirements.txt`; added `requirements-viz.txt`); ffmpeg 7.0.2 present;
   rclone `gdrive:` remote already configured.
5. Real recorded run (120 cmds): grounding 1.00, deadline-miss 0.467, latency
   mean 646 / p50 471 / p95 1102 ms. Wrote `assets/metrics.png` (committed),
   `outputs/replay.mp4` → Google Drive.
6. Finding: **bimodal latency** — group commands ~2× slower (more tokens),
   cross the 500 ms tick; single commands stay under it. Correct-but-late.
7. `pytest -q` → 8 passed.

**Outcome:** visual review pipeline in place; images in git, video on Drive.

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
