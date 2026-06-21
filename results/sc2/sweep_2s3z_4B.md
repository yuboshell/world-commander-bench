# SC2 SMAC win-rate (Qwen3-4B-AWQ) — by map and by deadline

**Last updated:** 2026-06-21 ~11:50 MDT (supervised calibration fix: world_range guard + calib-cap; bootstrap rescue confirmed, but force-proceed on failed calib degrades play — ~75% of runs clean)
**Machine:** yubopc (RTX 4060, 8 GB) · **SC2:** 5.0.15 (Base96883) · **Harness:** LLM-PySC2 (patched)
**Model/serving:** Qwen3-4B-AWQ via vLLM in WSL2 (`awq_marlin`, `--enforce-eager`,
`--gpu-memory-utilization 0.65`, offline); Windows pysc2 reaches it at `localhost:8001`.
Win/loss from the `obs-list-episode<N>-{win,lose,tie}.pkl` suffix; **~25.5 s/decision**
(deadline-independent — model inference cost). `WCB_SC2_MAX_WAIT` overrides the agent's
`MAX_LLM_WAITING_TIME` (wall-clock seconds the game waits for the LLM before `no_op`).

> The conclusion evolved as data arrived (an honest-science trail): "universal wall" →
> "map-dependent" → "moderate clock effect" → **final: capability-bound, deadline-invariant**
> (the MAX_WAIT=5 floor was decisive — see 3s5z below).
>
> **BOTTOM LINE (high-n, the verdict):** the 4B LLM's win-rate edge on balanced 3s5z is
> **~+10 pp and NOT statistically significant** (LLM-acts 49/64 vs no-effective-LLM 32/48,
> p≈0.25) — and it *shrank* as n grew (+22→+17→+10 pp; regression to the mean). Win-rate is
> **capability/matchup-bound**, not clock-bound. The reusable contribution is the validated
> **drop-late mechanism** (a true real-time clock), not a win-rate number. Intermediate figures
> below (e.g. the n≈28 "+20 pp, p≈0.11") are the trail to this verdict — see *Pooled real-time
> contrast* for the firmest statement.

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

**Implication:** the *true* drop-late frontier should fall from the LLM-acts win-rate (~77%) to
the LLM-dropped ≈ auto-attack floor (~67%) — unlike the flat soft-deadline frontier. The gap is
the LLM's contribution (**~+10 pp at high n, not significant** — see *Pooled real-time contrast*
below), small and noisy, so a clean fine-grained curve needs many episodes/point (hand-off).

**Drop-late frontier (3s5z) — mechanism robust, fine curve noise-limited:**
| MAX_WAIT | drop-late win | discards | note |
|---|---|---|---|
| 60 s | 14/16 (87%) | 0 | LLM acts on-time |
| 30 s | 4/8 (50%) | 0 | LLM acts on-time (0 drops) |
| 15 s | (12/16) | 0 | *invalid* — no bootstrap (0 LLM calls → auto-attack) |
| 10 s | 5/8 (62%) | 13 | replies dropped → ~auto-attack |

Auto-attack floor = 14/24 (58%). **The fine-grained frontier is noise-limited.** @60 (87%) and
@30 (50%) both have the LLM acting on-time with **0 drops**, yet differ by 37 pp — that spread is
**pure 8-episode sampling noise** (binomial ±~17–35 pp). At feasible n the noise **swamps** both
the LLM effect (~20 pp) and any deadline effect, so points bounce (87/50/62%) instead of tracing
a clean curve. **What *is* robust:** the drop-late *mechanism* (validated @10: 13/13 discarded,
attacks 45→1, win-rate → auto-attack) and the **extreme contrast** (no-drop LLM-acts vs
all-dropped LLM≈auto-attack). A clean curve needs **high n/point**, blocked by both sampling
noise *and* run-fragile calibration (~20–30% of runs never bootstrap). Hand-off.

## Pooled real-time contrast (high-n) — LLM-acts vs no-effective-LLM
The *core question* — does the LLM help **when it acts** vs **when the clock drops it / it's
absent**? — pooled across conditions, grown to n≈50–64/side:
- **LLM acts** (synchronous + drop-late @60, 0 drops): **49/64 (77%)**
- **No effective LLM** (drop-late @10 all-dropped + auto-attack `MAX_QUERIES=0`): **32/48 (67%)**

Contrast **+10 pp**; two-proportion z≈1.16, **p≈0.25 — not significant**. Critically, the effect
**shrank as n grew** (+22 → +17 → +10 pp): the early small-sample gaps were regression-to-mean,
and the auto-attack baseline is itself strong and noisy (per-batch win-rates 50/62/81%). **Honest
conclusion:** the 4B LLM's win-rate benefit on 3s5z is **real-but-small (~+10 pp) and NOT
statistically significant** even at controlled high n; detecting ~+10 pp at p<0.05 would need
n≈300+/side (infeasible on one 8 GB GPU). SC2 SMAC 3s5z is simply too auto-attack-dominated and
noisy for a 4B LLM's small edge to register. **The drop-late *mechanism* stays validated and
robust — that is the reusable contribution; the win-rate *magnitude* is an honest null/weak result.**

## Qualitative — what the 4B actually commands (why the edge is small)
Reading the LLM responses from a winning 3s5z run (`llm_log/…/CombatGroupSmac/a_raw.txt`, 21 decisions):
- **Tactically sensible, not incompetent:** every decision focus-fires the closest / lowest-health
  enemy and uses abilities reasonably (Zealot `Charge`, Stalker `Blink` to reposition) — e.g.
  *"focus on the Zealot with 5% health"*, *"Blink to attack from a safe distance"*.
- **But largely redundant with auto-attack:** "attack the nearest/weakest" is essentially what SC2
  units already do on their own, so the LLM mostly **commands what would happen anyway** — which is
  exactly why it adds only a small, non-significant edge. The genuine value-adds (Blink/Charge
  timing, focus-target choice) are real but marginal.
- **Occasional hallucination:** late-game it mislabels leftover enemies as "drones" in a
  Zealot/Stalker map — harmless here, but a sign the 4B loses track as state thins.

So the null is **redundancy, not incompetence**: the 4B plays reasonable, auto-attack-like micro.
A meaningfully larger edge would need decisions that *diverge* from the default (true kiting,
cross-team focus coordination) more reliably than this model produces.

## Latency — the real-time-viability bottleneck (the *clock* half of the thesis)
Per-decision cost (`cost.txt`, 3s5z, 21 decisions): **~27 s/decision** (range 25.5–30.1 s),
**prefill-dominated** — prompt = **2.4–5.7 K input tokens** (the full unit-by-unit observation),
output only ~150–315 tokens. Latency *falls* 29.5 → 25.5 s over the episode as units die and the
observation shrinks, so **latency scales with the observation size, not the generation**.

**Implication for World Commander — latency, not capability, is the binding real-time constraint.**
At ~27 s/decision the 4B is **~25× too slow** for second-scale RTS control (and ~5× too slow even
vs a generous 5 s deadline). This is *why* drop-late reverts the LLM to auto-attack at any deadline
< ~27 s (above). So the lever for real-time viability isn't only a smaller/faster model — it's
**shrinking the observation prompt** (prefill is the cost) and **KV-cache reuse across ticks**.
That is exactly the efficiency sweep (prompt size, KV-cache policy, VRAM budgets) the program
scopes next — and the headline pairing is: *the 4B is capable enough to roughly match auto-attack
but ~25× too slow to act in real time.*

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

## Calibration bootstrap — diagnosis + partial fix (supervised, 2026-06-21)
The camera/perception bootstrap is **multi-point fragile** — three independent gates, hit
intermittently run-to-run (each can leave the LLM never queried → 0-LLM auto-attack "data"):
- **(1) world_range==0** (`main_agent_funcs.py:220`): the heuristic computes 0 for some geometry
  (deterministic on 2s_vs_1sc) → stage 2.1 loops forever. **Fixed:** guard → fall back to the SMAC
  default 32 (`WCB_SC2_WORLD_RANGE`).
- **(2) coarse calibration never converges** (the 3s5z ~25% case): Path B (minimap) oscillates and
  never settles → stage 2.3 loops *thousands* of times → 0 LLM. **Mitigated:** `WCB_SC2_CALIB_CAP`
  force-proceeds to the LLM after N attempts.
- **(3) per-unit centering** (`get_camera_func_smart`) — a third gate that can loop after (2).

**What the cap buys (validated together):** it **guarantees bootstrap** — a forced-bad-calibration
test showed the cap fires and the LLM *is* queried past all gates (24 calls, 176 attacks). **But**
with *genuinely failed* calibration (offset 0,0) the LLM **lost 0/2** — mis-calibrated coords →
mis-clicks → bad play. So the cap converts a **0-LLM hang** into **degraded** data, not clean data.
Good news: natural convergence is fast (**<10 attempts**), so **~75% of runs calibrate fine** (cap
silent) → clean data. **Recipe:** run with `WCB_SC2_CALIB_CAP=50` to prevent hangs, but use
**cap-silent** runs for the clean win-rate (filter out cap-fired). **The real fix** — make Path B
converge (likely: do the analytic calibration from `unit_r`/raw coords so it doesn't need the unit
on-screen) — is the remaining deeper step.

## Suggested next steps (supervised session)
- **Fix the bootstrap fragility** (above) so every run reliably queries the LLM — unblocks a
  clean drop-late frontier + reliable win-rate on more maps.
- Then **drop-late** is ready (`WCB_SC2_DROP_LATE=1`, already implemented + validated): re-run the
  3s5z sweep at high n for a clean true frontier.
- More episodes/point to tighten CIs; a stronger model for 2s3z (won't fit 8 GB here).
- **Efficiency / latency sweep** (the real-time lever from the latency section): smaller models +
  shrunk observation prompt + KV-cache reuse across ticks. *Practical blocker found:* serving an
  **unquantized** model in this WSL2/vLLM env fails at engine init with `RuntimeError: UVA is not
  available` (the 4B's **AWQ** path avoids it). So a smaller-model latency test needs an **AWQ**
  quant — no official `Qwen3-1.7B-AWQ` exists, so source/build one (or debug the vLLM UVA path).
