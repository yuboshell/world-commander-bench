# SC2 SMAC win-rate (Qwen3-4B-AWQ) — by map and by deadline

**Last updated:** 2026-06-21 ~04:05 MDT (autonomous overnight run; 5-map controlled landscape complete)
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
| **3s_vs_3z** | 0 | **8** | 0 | yes (9 dec) | LLM controls units (kiting matchup), loses every game |
| **1c3s5z** | **8** | 0 | 0 | **no (0 dec)** | 8/8 win with the LLM never queried — **auto-attack alone wins** |
| 2s_vs_1sc | 0 | 0 | **8** | **no (0 dec)** | calibration never bootstrapped → idle → timeout ties |

### Auto-attack confound — controlled
SC2 units auto-attack, so a strong force can win with no LLM (1c3s5z = 8/8 and 2s_vs_1sc = 8
ties both resolved with the **LLM never queried**). A raw win therefore doesn't prove LLM skill —
hence no-LLM controls (MAX_QUERIES=0; 0 LLM calls verified):

| map | no-LLM (auto-attack) | with LLM (synchronous) | LLM effect |
|---|---|---|---|
| **3s5z** (balanced) | **14/24 (58%)** | **25/32 (78%)** | +20 pp — *suggestive, p≈0.11 (n.s.)* |
| 2s3z (unwinnable) | 0/8 (0%) | 0/16 (0%) | 0 — LLM neutral |
| 3s_vs_3z (unwinnable) | 0/8 (0%) | 0/8 (0%) | 0 — LLM neutral |
| 1c3s5z (overwhelming) | 8/8 (100%) | 8/8 (0 LLM) | none — auto-wins |
| 2s_vs_1sc (stalemate) | 8 ties | (calib failed) | n/a |

At n≈28/side the 3s5z LLM-vs-auto-attack gap (78% vs 58%) is **not statistically significant**
(two-proportion z≈1.6, p≈0.11; CIs overlap), and the LLM gets only **~1 decision/episode**
(camera overhead), capping its influence. **Cross-map pattern: win-rate tracks the force
matchup (the auto-attack baseline) — overwhelming auto-wins, unwinnable auto-loses, and only on
the *balanced* 3s5z does the LLM add a (modest, noisy) lift.**

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

## Drop-late (true real-time clock) — implemented + validated (2026-06-21 ~04:40 MDT)
The default LLM-PySC2 deadline is *soft* (a late reply is still applied), which is why win-rate
was deadline-invariant. I added an env-gated **drop-late** path (`WCB_SC2_DROP_LATE=1`): record
each query's fire-time + deadline and **discard** a reply that arrives past the deadline (a true
no_op), so a missed decision stays missed. (Patch: `agents/llm_pysc2_agent_main.py` +
`agents/llm_pysc2_agent.py`; default off → no change to existing behavior.)

**Validation (3s5z, MAX_WAIT=10, drop-late ON, 8 ep):** 13/13 late replies **discarded**
(logged), `Attack_screen` actions fell **45 → 1** (the LLM is effectively switched off), 0
errors. Win-rate 5/8 ≈ the auto-attack baseline (58%) — with the LLM dropped, the agent reverts
to auto-attack. So drop-late works: a deadline below the ~25 s latency removes the LLM's input.

**Implication:** the *true* drop-late frontier should fall from ~78% (loose deadline, LLM acts
in time) to ~58% (tight, LLM dropped = auto-attack) — unlike the flat soft-deadline frontier.
The gap is the LLM's contribution (~+20 pp), which is small/noisy, so a clean curve needs many
episodes/point (hand-off).

**Drop-late frontier (3s5z) — declining, vs the flat soft one:**
| MAX_WAIT | drop-late win | discards | note |
|---|---|---|---|
| 60 s | 14/16 (87%) | 0 | LLM acts on-time (= soft) |
| 15 s | (12/16) | 0 | *invalid* — calibration didn't bootstrap → 0 LLM calls (auto-attack run) |
| 10 s | 5/8 (62%) | 13 | replies dropped → ~auto-attack |

Auto-attack floor = 14/24 (58%). On the **valid** points (@60 LLM-on-time vs @10 LLM-dropped),
**drop-late traces a declining frontier — ~87% → ~62%** as the deadline crosses the ~25 s
latency, where the **soft deadline stayed flat (~75%)**: the clock only bites once it's enforced
as true drop-late. **Caveat:** the camera calibration is *run-fragile* — the @15 batch (and the
earlier 2s_vs_1sc / 1c3s5z) never queried the LLM at all, so a clean high-n drop-late curve is
**blocked until the calibration/centering is made reliable**. Directional result; hand-off.

## Conclusion
- **The 4B LLM's benefit is modest, noisy, and only on a *balanced* matchup.** Controlled vs
  auto-attack: 3s5z 58% → 78% (+20 pp, **p≈0.11 — not significant** at n≈28/side); 2s3z 0% → 0%
  (neutral); 1c3s5z auto-wins 8/8 (irrelevant); 2s_vs_1sc auto-ties. The LLM gets only ~1
  decision/episode (camera overhead), capping its influence. A meaningful LLM-SC2 score needs a
  balanced matchup, the auto-attack baseline controlled, **and many episodes** — otherwise
  "wins" are the game's default AI, and small samples over-state the model.
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
