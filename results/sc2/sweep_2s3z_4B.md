# SC2 SMAC win-rate (Qwen3-4B-AWQ) — by map and by deadline

**Last updated:** 2026-06-21 ~01:45 MDT (autonomous overnight run; 3s5z deadline sweep in progress)
**Machine:** yubopc (RTX 4060, 8 GB) · **SC2:** 5.0.15 (Base96883) · **Harness:** LLM-PySC2 (patched)
**Model/serving:** Qwen3-4B-AWQ via vLLM in WSL2 (`awq_marlin`, `--enforce-eager`,
`--gpu-memory-utilization 0.65`, offline); reached from Windows pysc2 at `localhost:8001`.
Win/loss from the saved `obs-list-episode<N>-{win,lose,tie}.pkl` suffix; latency ~25.5 s/decision
(deadline-independent — it's the model's inference cost). `WCB_SC2_MAX_WAIT` overrides the
agent's `MAX_LLM_WAITING_TIME` (wall-clock seconds the game waits for the LLM before `no_op`).

## ⚠️ Correction
An earlier version of this file concluded a "universal overhead/capability wall — the pipeline
can't win any map." **That was wrong**, overturned by the 3s5z result below. The pipeline
*does* win SMAC; win-rate is **map/matchup-dependent**.

## Win-rate by map (synchronous, MAX_WAIT=60 s, 8 episodes each)

| map | win | lose | tie | LLM queried? | note |
|---|---|---|---|---|---|
| **3s5z** | **8** | 0 | 0 | yes (19 dec, 131 attacks) | 4B **wins every game** |
| **2s3z** | 0 | **8** | 0 | yes (15 dec, 57 attacks) | LLM controls units, loses every game |
| 2s_vs_1sc | 0 | 0 | **8** | **no** (0 queries) | camera calibration never bootstrapped → idle → timeout ties |

**4B can win SMAC** (3s5z 8/8) — so the harness, perception, and 4B's micro are *good enough*
for some matchups. 2s3z is specifically unfavorable (0/8). A plausible mechanism: 3s5z's larger
force (8 units) is more resilient to the heavy per-decision overhead (~700 camera-calibration
moves + ~25 s inference, ~2 LLM decisions/episode), so the army survives long enough for the
LLM's sparse commands to win; 2s3z's smaller force and tighter micro do not. (2s_vs_1sc is a
separate calibration-bootstrap bug, not a capability datapoint.)

## 2s3z — deadline sweep (8 episodes/point)
| MAX_WAIT | win | lose | tie | timeouts→no_op | note |
|---|---|---|---|---|---|
| 60 s (sync) | 0 | 8 | 0 | 0 | LLM controls promptly, loses |
| 10 s (tight) | 0 | 8 | 0 | 26 | replies miss deadline, late control, loses |

2s3z is **deadline-invariant at 0** (the model can't win it even synchronously), so its frontier
is flat — not informative about the clock.

## 3s5z — deadline sweep (the informative frontier) — IN PROGRESS
Because 4B **wins** 3s5z synchronously, tightening the deadline below the ~25 s inference latency
should force `no_op`s and **drop the win-rate** — the clean real-time-clock effect on a winnable
map (the SC2 analog of the arena's deadline frontier). Sweeping MAX_WAIT = {60, 30, 15, 10}:

| MAX_WAIT | win/8 | status |
|---|---|---|
| 60 s | **8/8** | done (synchronous baseline) |
| 30 s | _running_ | |
| 15 s | _pending_ | |
| 10 s | _pending_ | |

## Conclusion so far
- **4B wins 3s5z 8/8 synchronously** → the LLM commander is viable for *some* SMAC matchups on
  SC2 5.0.15; the pipeline is not universally walled.
- **2s3z is lost 0/8 and deadline-invariant** → for that matchup the wall is capability +
  per-decision overhead, not the clock.
- The **3s5z deadline sweep** (in progress) tests the clock directly on a winnable map; a drop in
  win-rate as MAX_WAIT falls below ~25 s would be the real-game time-to-consequence frontier.

## Caveats
- 8 episodes/point (binomial noise; 0/8 and 8/8 are still strong signals).
- Heavy camera-calibration overhead means this measures the **pipeline**, not 4B's raw micro.
- Single model (4B); 2s_vs_1sc calibration bug unresolved.
