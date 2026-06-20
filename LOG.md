# Activity Log

Append-only record of work sessions. Newest first.

---

## 2026-06-19 — Report reordered (figure-first); SC2 reference codebases vendored

**Actions:**
1. Reordered `report.html` so the **grid replay comes first** (see it move),
   then the legend, then "what this is", results, config, metric definitions,
   breakdown, and charts last — intuition before jargon (`arena/viz.py`).
2. Vendored SC2 reference repos into gitignored `reference/`:
   `LLM-PySC2` (NKAI/NUDT; full PySC2 action space, async constant-latency query)
   and `TextStarCraftII` (Chain-of-Summarization; beats built-in AI to Lv5).
3. Added `pytest.ini` (`testpaths = tests`) so pytest ignores the vendored repos.
4. Regenerated + published the report. 13 tests pass.

**SC2 readiness (assessment):** not ready to run today, but well-positioned. Gaps:
install SC2 Linux + maps on amax41; stand up LLM-PySC2 (py3.9 env) pointed at our
vLLM; add our real-time layer (wall-clock deadline + drop late actions + VRAM
ceiling) on top — the arena's concurrent-clock TODO is the cheap rehearsal of it.
The efficiency sweep still needs our own controllable vLLM, not the shared one.

---

## 2026-06-19 — Add positive multi-agent command form (coverage gap)

**Goal:** Yubo noticed the sampler only issued single-target and all-except
commands — never a positive subset like "move the blue and green agents".

**Actions:**
1. TDD (`tests/test_commands.py`): added the positive-subset form to
   `arena/commands.py` (`_join_names` for natural lists; sampler now picks
   ~evenly among single / subset(2..N) / all-except).
2. Report breakdown now splits three forms (`arena/viz.py`).
3. Regenerated + published the report.

**Result (3-form run, 120 cmds):** grounding 1.00, deadline-miss **0.76** (up
from ~0.46 — multi-agent commands are now 72% of the stream). By form:
single 456 ms / miss 0.12; positive subset 1009 ms / miss 1.00; all-except
991 ms / miss 1.00. Any multi-agent order reliably blows the 500 ms tick;
single-target stays under. Grounding stays 1.00.

**Tests:** 13 passed.

---

## 2026-06-19 — report.html becomes the self-contained primary report

**Goal:** make the web page stand alone as the report Yubo reviews — explain the
experiment, the grey agents, and every chart/metric.

**Actions:**
1. Rewrote `build_html_report` (`arena/viz.py`) into a descriptive page: intro
   ("what this is"), run-configuration table (model/grid/agents/NPCs/tick/seed),
   metric definitions (grounding, latency, deadline miss), a grid legend
   (coloured = controlled, grey = NPC on its own clock, gold ring = commanded,
   fanned markers = same cell), both charts captioned, and a footer.
2. Added a **latency-by-command-type** table computed from the run.
3. Threaded run `meta` into the report; verified the rendered page with a headless
   browser screenshot (favicon 404 is the only console noise).
4. Regenerated + published to the unlisted Pages link.

**Result (120-cmd real run):** grounding 1.00, deadline-miss 0.46. Breakdown —
single-target: 76 cmds, mean 471 ms, miss 0.14; group/compositional: 44 cmds,
mean 1020 ms, **miss 1.00**. Every group command misses the 500 ms tick: the
bimodal latency is the compositional-addressing cost, now quantified.

---

## 2026-06-19 — Host the report for co-authors (unlisted GitHub Pages)

**Goal:** give co-authors a clickable link to the report instead of git-pull-and-open.

**Constraint:** the `DreamSoul-AI` org is on the free plan, so access-controlled
(login-gated) GitHub Pages is unavailable — any Pages site is public-by-URL.
Yubo chose the unlisted pattern (matches the research repo's proposal-article
decision): a dedicated public repo with an opaque slug + `noindex`, link as a
semi-secret password.

**Actions:**
1. Created a public repo with an opaque slug (under `yubohuangai`), pushed
   `report.html` as `index.html` + `robots.txt` (Disallow) + `.nojekyll`,
   enabled GitHub Pages. Verified live (HTTP 200, title, `noindex`, slider).
2. Added `noindex` to the report template (`arena/viz.py`).
3. `scripts/publish_report.sh` — repeatable publish; reads the target repo from
   `WCB_REPORT_REPO` in `.env` so the opaque slug never lands in git (this repo
   open-sources later). `.env.example` documents the optional var.
4. URL recorded in `.env` + Claude memory only, **not** in committed files.

**Outcome:** co-authors review by clicking a link; re-run + `publish_report.sh`
updates it.

---

## 2026-06-19 — Fix replay rendering; switch from video to a self-contained HTML report

**Goal:** Yubo found the MP4 hard to follow (frames too fast) and noticed
"move the red one" frames with no red shown; Drive download was inconvenient.

**Diagnosis:** not a model/grounding bug. The world has no collision rule, so
agents co-locate (51/120 frames); the renderer drew one marker per agent and
z-order hid co-located ones (12 frames hid the *commanded* agent). Grounding was
always 1.00 — only the drawing was lossy.

**Actions:**
1. TDD: added `Frame.targets` (commanded agents) so the renderer can highlight them.
2. `arena/viz.py` rewrite: fan co-located agents out within their cell; gold ring
   on the commanded agent(s); new `frame_data_uris` + `build_html_report`.
3. Output is now a self-contained `report.html` (committed) with an interactive
   grid viewer (slider / step / play at adjustable speed) — open after `git pull`,
   no Drive. Video is opt-in (`--mp4`, `--upload`).
4. Real recorded run (120 cmds): grounding 1.00, deadline-miss 0.49, latency
   mean 669 / p50 490 / p95 1100 ms. Wrote `report.html` (3.1 MB) + `assets/metrics.png`.
5. `pytest -q` → 9 passed.

**Outcome:** review is now offline, paced by the user, and faithful (every agent
visible). Drive video retired from the default path.

**Tradeoff noted:** `report.html` embeds 120 frames (~3 MB) and is re-committed
each run, so repo history grows. Trim frame count or move to git-LFS if it bites.

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
