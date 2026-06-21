# SC2 2s3z — deadline sweep / synchronous win-rate (Qwen3-4B-AWQ)

**Last updated:** 2026-06-21 ~01:15 MDT (autonomous overnight run; in progress)
**Machine:** yubopc (RTX 4060, 8 GB) · **SC2:** 5.0.15 (Base96883) · **Harness:** LLM-PySC2 (patched)
**Model/serving:** Qwen3-4B-AWQ via vLLM in WSL2 (`awq_marlin`, `--enforce-eager`,
`--gpu-memory-utilization 0.65`, offline mode); reached from Windows pysc2 at `localhost:8001`.

## Question
Disentangle **capability** (can a 4B LLM win 2s3z at all?) from **clock** (does the
real-time deadline cause the losses?). Method: sweep the agent's
`MAX_LLM_WAITING_TIME` (wall-clock seconds the game waits for the LLM before issuing
`no_op`) via the new `WCB_SC2_MAX_WAIT` env override. Large value ⇒ near-synchronous
(the ~25 s reply is used); small value ⇒ the reply lands too late ⇒ `no_op`.
Win/loss is read from the saved `obs-list-episode<N>-{win,lose,tie}.pkl` suffix.

## Results (8 episodes per deadline)

| MAX_WAIT | win | lose | tie | LLM decisions used | mean latency | note |
|---|---|---|---|---|---|---|
| **60 s (synchronous)** | **0** | **8** | 0 | ~15 total (~2/ep), 0 timeouts | ~25 s | LLM controls units (57 `Attack_screen`), still loses |
| 10 s (tight) | _pending_ | | | | | expect `no_op` (reply > deadline) |

## Findings (preliminary)
- **4B wins 0/8 even synchronously.** With the deadline effectively removed (MAX_WAIT=60,
  0 timeouts) the LLM *did* control units — it issued real combat micro (57 `Attack_screen`,
  plus select / control-group) — and **still lost every game**. So for 4B on 2s3z the
  binding wall is **not the LLM-wait deadline**.
- **Per-decision overhead dominates.** The agent spent ~**730 `move_camera` calls per
  episode** on calibration / per-unit centering vs only **~2 LLM combat decisions per
  episode**. The game advances during all that camera work, so units take fire and die
  before the LLM gets many moves in. Two of eight episodes also tripped
  "Detect Possible Endless Loop" (calibration hiccup). The loss is therefore driven by
  **framework per-decision cost (camera handling + ~25 s inference) against fast combat**,
  compounded by weak 4B micro — a real-time / time-to-consequence wall, not a tunable-deadline one.
- **Consistency with the arena.** Mirrors the arena's two theses: (1) macro/spatial play is
  capability-bound (4B is weak — arena macro ≈0.35), and (2) viability is set by
  time-to-consequence; 2s3z combat (seconds) is far inside the non-viable regime for this
  ~25 s/decision pipeline.

## Caveats
- Camera-calibration overhead dominates the step budget — this measures the *pipeline*
  (LLM-PySC2 + 4B + this hardware), not raw 4B tactical skill in isolation.
- Small sample (8 episodes/deadline); single model (4B); single map (2s3z).
- A win-rate-vs-deadline *frontier* is uninformative for 4B (0 synchronously ⇒ 0 at every
  tighter deadline); the tight-deadline row is included to show the *mechanism* (no_op vs
  controlled-but-outplayed), not a different rate.

## Next
- Add the MAX_WAIT=10 (tight) row.
- Optional: a more capable model (8B) synchronously — does added capability ever win 2s3z,
  or is the overhead/capability wall size-independent? (VRAM-permitting on the 8 GB card.)
- Optional: reduce camera-calibration overhead so the LLM gets more decisions/episode (would
  isolate capability better).
