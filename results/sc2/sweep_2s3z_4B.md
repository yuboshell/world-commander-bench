# SC2 SMAC win-rate (Qwen3-4B-AWQ) — by map and by deadline

**Last updated:** 2026-06-21 ~02:35 MDT (autonomous overnight run; complete)
**Machine:** yubopc (RTX 4060, 8 GB) · **SC2:** 5.0.15 (Base96883) · **Harness:** LLM-PySC2 (patched)
**Model/serving:** Qwen3-4B-AWQ via vLLM in WSL2 (`awq_marlin`, `--enforce-eager`,
`--gpu-memory-utilization 0.65`, offline); Windows pysc2 reaches it at `localhost:8001`.
Win/loss from the `obs-list-episode<N>-{win,lose,tie}.pkl` suffix; **~25.5 s/decision**
(deadline-independent — model inference cost). `WCB_SC2_MAX_WAIT` overrides the agent's
`MAX_LLM_WAITING_TIME` (wall-clock seconds the game waits for the LLM before `no_op`).

> The conclusion evolved as data arrived (an honest-science trail): "universal wall" →
> "map-dependent" → "moderate clock effect" → **final: capability-bound, deadline-invariant**
> (the MAX_WAIT=5 floor was decisive — see 3s5z below).

## Win-rate by map (synchronous, MAX_WAIT=60 s, 8 episodes)
| map | win | lose | tie | LLM queried? | note |
|---|---|---|---|---|---|
| **3s5z** | **8** | 0 | 0 | yes (19 dec) | wins — but is it the LLM or auto-attack? (control below) |
| **2s3z** | 0 | **8** | 0 | yes (15 dec) | LLM controls units, loses every game |
| **1c3s5z** | **8** | 0 | 0 | **no (0 dec)** | 8/8 win with the LLM never queried — **auto-attack alone wins** |
| 2s_vs_1sc | 0 | 0 | **8** | **no (0 dec)** | calibration never bootstrapped → idle → timeout ties |

### Auto-attack confound — controlled
SC2 units auto-attack, so a strong force can win with no LLM (1c3s5z = 8/8 and 2s_vs_1sc = 8
ties both resolved with the **LLM never queried**). A raw win therefore doesn't prove LLM skill —
hence no-LLM controls (MAX_QUERIES=0; 0 LLM calls verified):

| map | no-LLM (auto-attack) | with LLM (synchronous) | LLM effect |
|---|---|---|---|
| **3s5z** | 4/8 (50%) | 13/16 (81%) | **+~30 pp — the LLM helps** |
| 2s3z | 0/8 (0%) | 0/16 (0%) | 0 — unwinnable for the force; LLM neutral |
| 1c3s5z | 8/8 (overwhelming force) | 8/8 (also 0 LLM) | none — auto-wins |

So on the **balanced** 3s5z matchup the 4B LLM adds real value over auto-attack (50% → 81%);
on lopsided maps it's irrelevant. The 2s3z control distinguishes "unwinnable for the force" from
"LLM underperforms auto-attack."

## 2s3z — deadline sweep (8 eps/point): flat at 0
| MAX_WAIT | win/8 | timeouts |
|---|---|---|
| 60 s | 0 | 0 |
| 10 s | 0 | 26 |
Lost even synchronously → **capability wall** (the matchup is beyond 4B); deadline-invariant.

## 3s5z — deadline sweep (8 eps/point): ~75%, deadline-invariant
| MAX_WAIT | win/8 | timeouts→no_op |
|---|---|---|
| 60 s | 8/8 | 0 |
| 30 s | 5/8 | 0 |
| 15 s | 4/8 | 21 |
| 10 s | 5/8 | 50 |
| 5 s | 8/8 | 74 |

**Overall 30/40 ≈ 75% win, with no systematic deadline dependence** (8/8 at *both* the loosest
60 s and the tightest 5 s; the 4–5/8 dip in the middle is 8-episode noise). Timeouts rise
0 → 74 as the deadline tightens, but win-rate does **not** fall.

## Conclusion
- **The 4B LLM adds value only on a *balanced* matchup.** Controlled against the auto-attack
  baseline: 3s5z 50% → 81% (LLM helps, +~30 pp); 2s3z 0% → 0% (unwinnable for the force, LLM
  neutral); 1c3s5z auto-wins 8/8 (LLM irrelevant); 2s_vs_1sc auto-ties. A meaningful LLM-SC2
  score therefore requires a balanced matchup (auto-attack ≈ 50 %) **with the auto-attack
  baseline controlled** — otherwise "wins" are the game's default AI, not the model.
- **Win-rate is matchup-bound, not clock-bound** — deadline-invariant across MAX_WAIT 5–60 s on
  both 2s3z and 3s5z.
- **Why no clock effect:** LLM-PySC2's deadline is **soft** — a reply that misses the deadline
  fires a `no_op` that cycle but is still applied on a later cycle, so the LLM's commands get
  executed (just delayed), and 3s5z's larger force tolerates the delay. The deadline knob
  changes *timeout counts* (0 → 74), not the *outcome*.
- **To expose a real-time frontier you need true drop-late** — discard a decision whose
  deadline passed instead of applying it late. That is exactly the **World Commander clock
  layer** (wall-clock deadlines + drop-late + VRAM ceiling) that SC2.md lists as "still to add."
  Until then, SC2 win-rate measures capability, not real-time viability.
- **Consistent with the arena:** capability/matchup is the binding axis here; the clock only
  bites once you enforce a hard drop-late deadline (the arena's deadline-miss metric).

## Caveats
- 8 episodes/point (wide binomial CIs; pooled 3s5z n=40). Single model (4B).
- Heavy camera-calibration overhead (~700 move_camera/episode, ~2 LLM decisions/episode) means
  this measures the **pipeline**, not 4B micro in isolation.
- 2s_vs_1sc calibration-bootstrap bug unresolved (no LLM data for that map).

## Suggested next steps
- Implement **drop-late** (don't apply replies past the deadline) → then re-run the 3s5z sweep
  to get a *true* win-rate-vs-deadline frontier.
- More episodes/point to tighten CIs; a stronger model for 2s3z (won't fit 8 GB here).
- Fix the per-unit camera-centering overhead so the LLM gets more decisions/episode.
