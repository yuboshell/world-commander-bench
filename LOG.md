# Activity Log

Append-only record of work sessions. Newest first.

---

## 2026-06-20 (overnight) — ⚠️ GitHub account suspended; switched to local-only

`git push` failed: "Your account is suspended." Account-level, needs Yubo to
contact GitHub Support. See `ALERT-github-suspended.md`. No data lost — work keeps
committing locally (ahead of origin); the published report is frozen at the last
successful publish. The loop continues local experiments + local commits and tries
one push per iteration to detect reinstatement, then resumes push/publish.

---

## 2026-06-20 (overnight autonomous) — first real SC2 LLM latency numbers

**Correction to the prior entry:** the "2s3z smoke, 120 LLM actions" did NOT
exercise the LLM (those were camera-calibration moves; vLLM saw 0 requests).

**Debug + fix:** SMAC camera calibration never converges on SC2 4.10, so the agent
never reached the LLM decision phase. Added a calibration cap
(`WCB_SC2_CALIB_CAP`) in `main_agent_funcs.py` to force-proceed after N steps;
raised `MAX_LLM_QUERY_TIMES`; added per-decision metric logging (latency, tokens)
to `gpt_query_runtime` → `outputs/sc2_*.jsonl`. (pvz maps segfault SC2 4.10 —
version mismatch; SMAC loads fine.)

**First real SC2 numbers (Qwen3-4B-AWQ, 2s3z, 9 decisions, 0 errors):**
~6 s per decision (6149 / 5578 ms …), **~4000 input tokens** (state + wiki) /
~230 output tokens. SC2 context makes a decision ~10x the arena (~0.5 s) — the
efficiency wall the program targets, now measured. Win-rate not yet meaningful
(calibration capped → imperfect centering); latency/tokens are valid. Recipe +
caveats in `SC2.md`. Synchronous clock (game waits for model) — real-time layer next.

**Next (this session):** accumulate more decisions, build an SC2 latency report
section, then schema/model sweeps at SC2 context scale.

---

## 2026-06-20 — StarCraft II bring-up: 2s3z smoke test passing

**Milestone:** the SC2 testbed runs end-to-end against our own vLLM.

**Done:**
1. Installed SC2 4.10 Linux (`Base75689`) at `/mnt/yubo/StarCraftII`; copied
   LLM-PySC2's `llm_smac`/`llm_pysc2` maps into `$SC2PATH/Maps`.
2. conda `llm-pysc2` (py3.9) + `pip install -e reference/LLM-PySC2` + `sniffio anyio`.
3. Patched the vendored repo (see `SC2.md`): Qwen3 no-think + max_tokens in the
   OpenAI call; FACTORY fallback to GptClient for arbitrary served ids;
   `2s3z.py` points at our vLLM (env-overridable).
4. Served Qwen3-4B-AWQ on GPU 2 (port 8001), ran `2s3z` headless.

**Result:** SC2 launched headless, the LLM agent issued **120 actions, 0 errors /
fallbacks / thinking-mode blowups**, episode completed, replay saved, clean exit.
Pipeline confirmed: SC2 ↔ pysc2 ↔ LLM-PySC2 ↔ our vLLM. Recipe in `SC2.md`.

**Not yet:** this is a "does the loop drive the game" smoke test, not the
benchmark. Next: port the arena's real-time layer (wall-clock deadline, drop late
actions, VRAM ceiling, metrics) onto it; scale the model for win-rate; KV-cache sweep.

---

## 2026-06-19 — Our own vLLM up; model-size frontier overlay

**Goal:** overlay frontiers across model sizes — needs our own controllable vLLM.

**Actions:**
1. Stood up our own vLLM on the free **GPU 2** (port 8001), separate from the
   shared inventory-bot instance (GPUs 0/1, port 8000).
2. `scripts/serve_sweep.sh` — serve each size on GPU 2, run the arena, tear down
   (teardown scoped to GPU 2 + port 8001 only, never the shared server).
   `scripts/run_one_model.py` runs one endpoint -> compact JSON.
3. Generalized the report: `build_html_report` takes stackable `extra_sections`;
   the overlay plot takes generic titles. `scripts/build_report.py` assembles the
   full report (baseline body + schema overlay + model-size overlay) and publishes.
4. Sized Qwen3 0.6B/1.7B (fp16) + 4B/8B (AWQ) on GPU 2 + 14B (shared).

**Result (90 cmds, JSON schema):** 0.6B g=0.58/966ms; 1.7B g=0.41/737ms;
**4B g=1.00/560ms**; 8B g=1.00/567ms; 14B g=1.00/936ms. Grounding collapses below
4B; latency is not monotone in size (4B/8B on a dedicated GPU beat the shared
TP=2 14B). **4B dominates** on this hardware. 22 tests pass.

---

## 2026-06-19 — Output-schema comparison: overlaid frontiers (first method result)

**Goal:** overlay deadline frontiers for different output schemas to test whether
a terser reply format beats the latency wall.

**Actions (TDD):**
1. `arena/model_client.py` — schema registry (json / pairs / grouped) with system
   prompt + parser each; `RealClient(schema=...)`. Parsers TDD'd
   (`tests/test_schemas.py`): `parse_pairs` ("red:N"), `parse_grouped` ("N: red blue").
2. `arena/viz.py` — `plot_schema_frontiers` (overlay, all + multi-agent panels);
   `build_html_report` gained an optional "Output-schema comparison" section.
3. `scripts/schema_sweep.py` — runs each schema on the same command stream,
   builds the overlay + table, regenerates + publishes the report.

**Result (90 cmds/schema, all grounding 1.00):** json p50 919 ms, miss@500 0.70;
pairs p50 298 ms, miss 0.03; grouped p50 259 ms, miss 0.01. Terse schemas are
**~3.5× faster with no grounding loss** — the "multi-agent infeasible" wall was
JSON verbosity, not the task. 22 tests pass.

---

## 2026-06-19 — Deadline-frontier curve added to the report

**Goal:** answer "is 500 ms too strict?" with a curve instead of a single number.

**Actions (TDD):**
1. `arena/metrics.py` — `miss_rate(latencies, deadline)` (post-hoc threshold;
   `tests/test_metrics.py`). The whole frontier is free from one run's latencies.
2. `arena/viz.py` — `plot_deadline_frontier` (miss rate vs budget, split all /
   single-target / multi-agent, with the current-deadline marker). New
   "Deadline frontier" section in `report.html`; `assets/frontier.png` committed.
3. `scripts/visualize.py` wires it in. Regenerated + published.

**Finding:** single-target commands are feasible at ~500 ms; multi-agent commands
need ~1500 ms. 500 ms is a *discriminating* point (singles pass, multi fail), not
necessarily "too strict" — the point is to report the frontier, not one deadline.
18 tests pass.

---

## 2026-06-19 — Concurrent clock implemented (the world no longer pauses)

**Goal:** make the arena's clock truly unpausable — the world advances while the
model thinks, the shared real-time primitive SC2 needs.

**Actions (TDD, `tests/test_clock.py`):**
1. `arena/clock.py` — `ConcurrentClock`: a daemon thread that ticks NPCs every
   `tick_ms` of wall-clock time; tracks `ticks`; clean start/stop.
2. `arena/world.py` — `GridWorld` now thread-safe (an `RLock` guards
   apply/tick_npcs/render_text/snapshot).
3. `arena/harness.py` — `run_session` starts the clock and runs commands while it
   ticks; **separate RNGs** for the command stream vs NPC moves so the two threads
   never share random state. `concurrent=True` by default; `concurrent=False`
   keeps the deterministic one-tick-per-command fallback.
4. Regenerated + published the report (replay now shows NPCs drifting during the
   model's think, not frozen between commands).

**Effect:** a slow response now *concedes ground* — the NPCs move during the
~0.5–1 s think, so the next decision faces a changed world, not just a dropped
action. 17 tests pass.

**Decision logged** in the research repo's DECISIONS.md (SC2-readiness +
sequencing: arena concurrent clock first, then LLM-PySC2 bring-up, then our
real-time layer; efficiency sweep needs our own vLLM).

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

---

## 2026-06-21 (overnight, autonomous) — plan

Guardrails in force (post-suspension): commit locally often, **push to GitLab per
milestone only** (no bursty pushes), **never auto-create public repos/Pages**, **GPU 2
only** (GPU 0/1 + `:8000` are the shared bot — leave alone). amax-side work only
(SC2 win-rate is yubopc's).

Backlog (highest value first):
1. **Hierarchy router** — route micro→small/fast (4B), macro→large/capable (14B);
   compare vs single-model baselines (`RouterClient`, `scripts/hierarchy_sweep.py`).
   Tests the architecture the macro-capability curve motivated. [running]
2. **Burst-load model** — reframe the command-stream load from sustained rate to
   crisis bursts; `simulate_stream` takes arbitrary arrivals. Pure-Python + replay, TDD.
3. **KV-cache / VRAM efficiency sweep** — vary serving knobs on GPU 2, measure
   latency/throughput at SC2-scale context (the stated efficiency-sweep TODO).
4. **Combined micro+macro capability curve** (same fresh methodology, all sizes).
5. Memory / region commands (`commands.py` TODO); research synthesis.

### entry — hierarchy router built (TDD, 38 green)
`RouterClient` (micro→small, macro→large) + `hierarchy_sweep.py` (3 policies over one
fixed half-micro/half-macro stream, fresh states). GPU eval launching (4B on GPU 2 +
14B on `:8000`).

### result — hierarchy router Pareto-dominates (n=80)
router grounding 0.73 = large-only's, at p50 1000 ms vs large's 1213 ms (micro half
556 ms vs 944 ms on 14B). Buys the big model only for macro. In REPORT.md.

### entry — burst-load model (item 2, TDD, 8 rate tests)
`simulate_arrivals` + `burst_arrivals` + `burst_sweep.py`. At a 2 s deadline a fast
model clears bursts of ~3 commands; bigger flurries blow the deadline (backlog).

### milestone push — hierarchy + burst (calm cadence; no public repos)
Next: KV-cache/VRAM efficiency + latency-vs-context (item 3) on GPU 2.

### result — context-latency + prefix-cache catch (item 3)
True prefill ~linear (~0.2 ms/token): latency 347→1417 ms over 185→5250 input tokens.
**Caught an artifact**: the first run was flat (~340 ms) because repeated identical
prompts hit vLLM's prefix cache; re-ran with unique prompts + `--no-enable-prefix-caching`
for the true curve. Lever: prefix-cache the static prefix (system + wiki) for SC2; and
input context is a modest, cacheable cost — output length is the bigger latency driver.
In REPORT.md. (milestone push)
Next: KV/VRAM concurrency or combined micro+macro capability curve (item 4).

### result — prefix-cache saving quantified
~4580-token static prefix: 1212 ms uncached vs 285 ms cached -> ~927 ms (76%) saved
per decision (`scripts/prefix_cache_sweep.py`). Concrete SC2 lever (static system+wiki
prefix). Consistent with the context-latency curve. (milestone push)
Next: combined micro+macro capability curve, or memory/region commands.

### result — region commands: reference solved, planning is the cliff
4B fresh (n=120): micro 1.00, region 0.97, macro 0.38. Spatial *reference* (top half /
nearest centre) is ~solved; goal *planning* is the cliff. Refines "macro is hard" ->
planning, not perception. REGION_FORMS + granularity_grid.py. (milestone push)
