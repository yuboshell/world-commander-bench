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
| Real, 500 ms tick (single+all-except mix) | 200 | 1.00 | 0.385 | 609 ms | 444 ms | 1079 ms |
| **Real, recorded (3-form mix)** | **120** | **1.00** | **0.758** | **851 ms** | **927 ms** | **1237 ms** |

Saved: `runs/qwen3-14b-awq_200.json` (gitignored). The 200-cmd run predates the
positive-subset command form, so it is single-heavy; the 120-cmd run samples all
three forms ~evenly, which is why its deadline-miss is much higher. Latency is
wall-clock on a GPU shared with the inventory bot, so numbers vary run to run.

### Reading the numbers
- **Grounding 1.00** — at the current scale (8×8 grid, 4 agents, 4 NPCs) the model resolves every command (single-target and "all-except" group forms). Deterministic (temperature 0).
- **Deadline misses ~0.39** — ~40% of commands exceed the 500 ms tick budget. p50 (444 ms) sits right on the line, so the rate is sensitive and wobbles run-to-run (observed 0.385–0.425) under shared-GPU contention. p95 ~1080 ms is the tail.
- **Mock** numbers validate plumbing only: `MockClient` returns ground truth with p=0.9 instantly.

## Key finding — Qwen3 thinking mode
The first real run gave **grounding 0.0, 100% deadline miss, ~4000 ms latency**. Root cause: Qwen3-14B defaults to *thinking* mode and spent the entire 128-token budget inside `<think>` (`finish_reason: length`), never emitting the JSON → `parse_moves` returned empty every time.

**Fix:** `RealClient.act` now passes `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`. Verified: the model then returns `[{"agent":"red","dir":"N"}]` in 12 tokens (`finish: stop`). Grounding 0.0 → 1.0; latency ~4000 ms → ~600 ms.

## Visualization

`python scripts/visualize.py --commands 120` records per-tick state and emits:

- **`report.html`** (committed, self-contained) — **the primary report**: open it
  in a browser after a `git pull` (or via the hosted link). It is fully
  self-explanatory — what the arena is, the run configuration, every metric
  defined, a latency-by-command-type breakdown, a grid legend (what the grey
  agents and gold rings mean), the charts explained, and an interactive
  grid-replay viewer (slider / step / play at adjustable speed).
- **`assets/metrics.png`** (committed) — latency histogram with the tick budget +
  percentiles, and a per-command latency timeline coloured on-time vs miss.
- Video is opt-in: `--mp4` writes `outputs/replay.mp4`; `--upload` pushes it to
  Google Drive. The default path produces no video.
- **Hosted copy** for co-authors: `scripts/publish_report.sh` mirrors `report.html`
  to an *unlisted* GitHub Pages site (opaque slug + `noindex`; link treated as a
  semi-secret password). The URL is **not** committed here — it lives in `.env`
  (`WCB_REPORT_REPO`) so it does not leak when this repo open-sources. Ask Yubo
  for the link.

![latency metrics](assets/metrics.png)

**Rendering note.** The world has no collision rule, so agents can share a cell
(~half of frames). The renderer fans co-located agents out within their cell and
rings the commanded agent(s) in gold — earlier frames hid agents under one
another, which is why a "move the red one" frame could show no red. The grounding
logic was always correct; only the drawing was lossy.

**Finding — latency scales with how many agents a command names.** Split by form
(3-form run): single-target 456 ms (miss 0.12); positive subset 1009 ms
(miss 1.00); all-except group 991 ms (miss 1.00). Any **multi-agent** command —
whether a positive subset ("the blue and green agents") or the all-except group —
emits more tokens and reliably blows the 500 ms tick, while single-target stays
under it. Grounding stays 1.00 throughout: the model is *correct but late* on
multi-agent orders — exactly the real-time-clock pressure the arena exposes.
A natural method probe: a terser output schema to pull multi-agent latency back
under the tick.

**Command forms.** The sampler issues three forms, sampled ~evenly: single-target,
a positively named subset (sizes 2..N), and all-except. (Earlier runs only had
single + all-except, missing positive subsets like "move the blue and green ones".)

**Deadline frontier.** The 500 ms deadline is the scaffold default (it matches
AVA's ~2 Hz VLM-commander cadence), not a derived value. Since a miss is just
`latency > deadline`, the whole miss-rate-vs-budget curve is computable post-hoc
from one run — this is the benchmark's real output (performance vs budget), not a
single number. On this setup, single-target commands are feasible at ~500 ms
while multi-agent commands need ~1500 ms. The curve shifts with model size, GPU,
and output verbosity.

![deadline frontier](assets/frontier.png)

**Output schema is the dominant latency lever (method result).** Running the same
task under three reply formats (`scripts/schema_sweep.py`), all at grounding 1.00:

| schema | example | p50 latency | miss@500ms |
|---|---|---|---|
| json (verbose) | `[{"agent":"red","dir":"N"}]` | 919 ms | 0.70 |
| pairs | `red:N blue:N` | 298 ms | 0.03 |
| grouped | `N: red blue` | 259 ms | 0.01 |

Switching from verbose JSON to a terse format cuts latency **~3.5×** with **no loss
of grounding**, pulling almost all commands (including multi-agent) back under the
500 ms deadline. The earlier "multi-agent commands are infeasible" result was an
artifact of JSON verbosity, not the task. The whole frontier shifts left:

![schema frontier overlay](assets/schema_frontier.png)

**Model size — 4B is the sweet spot (our own vLLM on GPU 2).** Sweeping Qwen3
sizes (verbose JSON schema, 90 cmds; ≤1.7B fp16, ≥4B AWQ on one 2080 Ti, 14B from
the shared TP=2 instance):

| model | grounding | p50 latency | miss@500ms |
|---|---|---|---|
| 0.6B | 0.58 | 966 ms | 0.70 |
| 1.7B | 0.41 | 737 ms | 0.68 |
| **4B** | **1.00** | **560 ms** | 0.60 |
| 8B | 1.00 | 567 ms | 0.62 |
| 14B | 1.00 | 936 ms | 0.71 |

Two findings: (1) **grounding collapses below 4B** — 0.6B/1.7B cannot reliably
follow commands, while 4B and up are perfect; (2) on this hardware **latency is
not monotone in size** — 4B/8B (AWQ, dedicated GPU) are *faster* than 14B (bigger,
TP=2, shared with the inventory bot), and the tiny fp16 models aren't fast either.
So 4B dominates: smallest model that keeps grounding, and the lowest latency. The
frontier is hardware-specific (it will move on a 4060/H100), which is exactly why
results are reported vs budget. (The frontier curve below reflects latency only;
read it together with the grounding column.)

![model-size frontier overlay](assets/model_frontier.png)

## Validation
- `pytest -q` → 8 passed (world, grounding, recorder).

## Next steps (open TODOs from CLAUDE.md / code)
- ~~Concurrent clock~~ **done** — the world now ticks NPCs on a real timer
  thread during the model's think (`arena/clock.py`); a slow response sees a
  changed world. Pass `concurrent=False` for the old one-tick-per-command mode.
- ~~Positive multi-agent command form~~ **done**; ~~per-tick capture for viz~~ **done**.
- Explicit command-rate control (issue at a target rate, queue overruns).
- Memory / region commands.
- StarCraft II bring-up: install SC2 Linux + maps; stand up `reference/LLM-PySC2`
  pointed at our vLLM; port the real-time deadline layer on top.
- Efficiency sweep (KV-cache policy, VRAM budgets) — needs our **own** controllable vLLM, not the shared instance.
