# SC2 2s3z — deadline sweep / synchronous win-rate (Qwen3-4B-AWQ)

**Last updated:** 2026-06-21 ~01:25 MDT (autonomous overnight run)
**Machine:** yubopc (RTX 4060, 8 GB) · **SC2:** 5.0.15 (Base96883) · **Harness:** LLM-PySC2 (patched)
**Model/serving:** Qwen3-4B-AWQ via vLLM in WSL2 (`awq_marlin`, `--enforce-eager`,
`--gpu-memory-utilization 0.65`, offline mode); reached from Windows pysc2 at `localhost:8001`.

## Question
Disentangle **capability** (can a 4B LLM win 2s3z at all?) from **clock** (does the
real-time deadline cause the losses?). Method: sweep the agent's `MAX_LLM_WAITING_TIME`
(wall-clock seconds the game waits for the LLM before issuing `no_op`) via the new
`WCB_SC2_MAX_WAIT` env override. Large ⇒ near-synchronous (the ~25 s reply is used);
small ⇒ the reply lands too late ⇒ `no_op`. Win/loss is read from the saved
`obs-list-episode<N>-{win,lose,tie}.pkl` suffix; latency from the metrics JSONL.

## Results (8 episodes per deadline)

| MAX_WAIT | win | lose | tie | LLM decisions (logged) | mean latency | timeouts→no_op | note |
|---|---|---|---|---|---|---|---|
| **60 s (synchronous)** | **0** | **8** | 0 | 15 (~2/ep) | 25.6 s | 0 | LLM controls promptly — 57 `Attack_screen` — still loses |
| **10 s (tight)** | **0** | **8** | 0 | 13 | 25.0 s | 26 | replies miss the deadline → late/delayed control (45 `Attack_screen`) — still loses |

## Findings
- **Win-rate is deadline-invariant at 0** (0/8 at both 60 s and 10 s). Removing the clock
  (synchronous, 0 timeouts) does **not** help, so for 4B the binding wall is **not the
  LLM-wait deadline** — it's capability + per-decision overhead.
- **Mechanism differs, outcome doesn't.** At 60 s the LLM controls units promptly; at 10 s
  its ~25 s replies miss the 10 s deadline and are applied late (26 timeouts) — either way
  every game is lost.
- **Per-decision overhead dominates.** The agent spends ~**730 `move_camera` calls/episode**
  on calibration / per-unit centering vs only ~**2 LLM combat decisions/episode**; the game
  advances throughout, so units take fire and die before the LLM gets many moves in (2/8
  episodes also tripped "Detect Possible Endless Loop"). Latency is deadline-independent
  (~25.5 s) — it's the model's inference cost, not the wait.
- **Consistent with the arena.** Mirrors the two arena theses: macro/spatial play is
  capability-bound (4B macro ≈ 0.35), and viability is set by time-to-consequence — 2s3z
  combat (seconds) sits deep in the non-viable regime for this ~25 s/decision pipeline.

## Caveats
- Camera-calibration overhead dominates the step budget, so this measures the **pipeline**
  (LLM-PySC2 + 4B + this hardware), not 4B's raw tactical skill in isolation.
- Small sample (8 eps/deadline); single model (4B); single map (2s3z).
- The win-rate-vs-deadline *frontier* is flat at 0 for 4B (0 synchronously ⇒ 0 everywhere);
  the deadline rows show the *mechanism* (no_op/late vs prompt), not a different rate.

## Next
- **`2s_vs_1sc` (easiest SMAC map), synchronous** — does 4B win *anything*? Distinguishes
  "2s3z is too hard for 4B" from "the pipeline/overhead can't win any map." (In progress.)
- Optional: reduce camera-calibration overhead to give the LLM more decisions/episode and
  better isolate capability; a larger model is not testable here (8B≈4B at macro; 14B won't
  fit the 8 GB card).
